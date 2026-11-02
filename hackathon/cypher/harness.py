"""The harness: the code around the model that decides what it sees, checks its work, and asks for help.

    examples -> model writes Cypher -> execute -> rows? done
                                         | no
                                    arrow fix (no model call) -> rows? done
                                         | no
                                    repair: error/empty + hints -> model, up to N times
                                         | still no
                                    escalate: the same loop on a bigger model

Honesty rule: nothing here sees the gold answer. Decisions use only errors, empty results and the schema.
Grading happens afterwards in run_eval.py.
"""
from dataclasses import dataclass, asdict
from typing import Optional
import time

import fixes
from executor import execute
from score import clean_pred

SYSTEM = """You translate questions into Cypher queries for a Neo4j graph database.
Rules:
- Use only the node labels, relationship types and properties listed in the schema.
- Follow relationship directions exactly as the schema lists them.
- Return only the Cypher query, with no explanation."""


@dataclass
class Config:
    shots: int = 0                  # retrieved examples in the prompt
    fix: bool = False               # arrow-direction fix on empty results
    repair: int = 0                 # max repair rounds per model
    escalate: Optional[str] = None  # model to hand failures to
    warn: bool = False              # treat "ran, but the database warned" (e.g. unknown property) as a failure

    def as_dict(self):
        return asdict(self)


def build_messages(row, examples):
    """The first prompt. Training data (FT1-FT3) uses this same function, so train and test prompts match."""
    shots = "".join(f"Question: {e['question']}\nCypher: {e['cypher']}\n\n" for e in examples)
    shots = f"Examples from the same database:\n\n{shots}" if shots else ""
    user = f"Schema:\n{row['schema']}\n\n{shots}Question: {row['question']}\nCypher:"
    return [{"role": "system", "content": SYSTEM}, {"role": "user", "content": user}]


def repair_message(attempt, row, value_hints):
    if attempt["status"] == "error":
        problem = f"Running your query failed with this error:\n{attempt['error']}"
    elif attempt["status"] == "warn":
        problem = "Your query ran, but the database warned:\n" + "\n".join(f"- {w}" for w in attempt["warnings"])
    else:
        problem = "Running your query returned no rows."
    notes = fixes.schema_hints(attempt["cypher"], row["schema"]) + value_hints
    notes = "\n".join(f"- {n}" for n in notes)
    notes = f"\nNotes:\n{notes}" if notes else ""
    return f"{problem}{notes}\nWrite a corrected Cypher query. Return only the query."


class Harness:
    def __init__(self, cfg, llm, escalate_llm=None, retriever=None, tracer=None):
        self.cfg, self.llm, self.escalate_llm = cfg, llm, escalate_llm
        self.retriever, self.tracer = retriever, tracer

    # ----- one database query, traced -----
    def _run(self, graph, cypher, source):
        with self.tracer.step(f"execute ({source})", as_type="tool", input=cypher) as obs:
            res = execute(graph, cypher)
            if not res["ok"]:
                status = "error"
            elif not res["rows"]:
                status = "empty"
            else:
                status = "warn" if self.cfg.warn and res["warnings"] else "rows"
            obs.update(output={"status": status, "error": res["error"], "n_rows": len(res["rows"]),
                               "rows": res["rows"][:5], "warnings": res["warnings"]})  # first 5 rows, for reading traces
        return res, status

    @staticmethod
    def _record(res, status, **fields):
        """One attempt as stored in the result file."""
        return {**fields, "status": status, "error": res["error"], "warnings": res["warnings"],
                "n_rows": len(res["rows"]), "_result": res}  # full result: graded, then dropped, by run_eval.py

    # ----- one model call plus its execution -----
    def _attempt(self, llm, messages, row, source):
        with self.tracer.step(source, as_type="generation", model=llm.name, input=messages) as gen:
            reply = llm(messages)
            gen.update(output=reply.text, usage_details={"input": reply.in_tokens, "output": reply.out_tokens},
                       cost_details={"total": reply.cost})
        cypher = clean_pred(reply.text)
        t0 = time.time()
        res, status = self._run(row["graph"], cypher, source)
        return self._record(res, status, source=source, model=llm.name, output=reply.text, cypher=cypher, calls=1,
                            in_tokens=reply.in_tokens, out_tokens=reply.out_tokens, cost=reply.cost,
                            secs=reply.secs + time.time() - t0)

    def _value_hints(self, attempt, row):
        if attempt["status"] != "empty":
            return []
        hints = []
        for label, prop, value, q in fixes.value_lookups(attempt["cypher"]):
            res = execute(row["graph"], q)
            found = [r["value"] for r in res["rows"]] if res["ok"] else []
            if found and value not in found:
                hints.append(f"No {label}.{prop} equals '{value}'. Similar stored values: {found}")
        return hints

    # ----- the loop for one model: first try, arrow fix, repairs -----
    def _loop(self, llm, row, first_messages, prefix):
        attempts = []
        messages = list(first_messages)
        a = self._attempt(llm, messages, row, prefix + "first")
        attempts.append(a)
        if a["status"] == "rows":
            return attempts
        if self.cfg.fix:
            fixed = fixes.flip_arrows(a["cypher"], row["schema"])
            if fixed != a["cypher"]:
                t0 = time.time()
                res, status = self._run(row["graph"], fixed, prefix + "fix")
                attempts.append(self._record(res, status, source=prefix + "fix", model=None, output=None, cypher=fixed,
                                             calls=0, in_tokens=0, out_tokens=0, cost=0.0, secs=time.time() - t0))
                if status == "rows":
                    return attempts
        seen = {a["cypher"]}
        for i in range(self.cfg.repair):
            a["feedback"] = repair_message(a, row, self._value_hints(a, row))  # kept so FT3 can replay the turn
            messages += [{"role": "assistant", "content": a["output"]}, {"role": "user", "content": a["feedback"]}]
            a = self._attempt(llm, messages, row, f"{prefix}repair{i + 1}")
            attempts.append(a)
            if a["status"] == "rows" or a["cypher"] in seen:
                break  # solved, or the model is repeating itself
            seen.add(a["cypher"])
        return attempts

    def solve(self, row, exclude_ids=()):
        """Run every enabled stage on one question. Returns the list of attempts, in order."""
        examples = []
        if self.cfg.shots and self.retriever:
            with self.tracer.step("retrieve", as_type="retriever", input=row["question"]) as obs:
                examples = self.retriever.top(row["question"], row["graph"], self.cfg.shots, exclude_ids)
                obs.update(output=[e["id"] for e in examples])
        first = build_messages(row, examples)
        attempts = self._loop(self.llm, row, first, "")
        if self.escalate_llm and not any(a["status"] == "rows" for a in attempts):
            attempts += self._loop(self.escalate_llm, row, first, "escalate:")
        return attempts, [e["id"] for e in examples]
