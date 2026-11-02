"""Wrap the harness in spans without editing it.

The harness functions are left untouched. This module swaps the names in the `harness`
module namespace for wrappers that open a span, call the original, and record what came
back. Because `harness.py` calls its own helpers through module globals
(`vote3` calls `generate_and_repair`, which calls `_exec`), replacing the attribute is
enough to trace the whole chain.

Span tree per question:

    text2cypher                      root trace: question, graph, tier, config
      route                          escalated?, big model
        vote                         per-attempt result, agreement
          attempt                    x3, in parallel
            schema_prune             chars before/after
            generate   (generation)  model, prompt/completion tokens, cost
            validate                 problems found
            execute                  query, status, row count, latency
            repair     (generation)  second model call
            validate
            execute
        attempt                      the big model, only when escalated

Nothing here runs unless the caller imports it, so the harness's own entry points are
unaffected. Every wrapper is a straight pass-through when tracing is off.
"""
import csv, datetime, json, os, sys, threading, time

HERE = os.path.dirname(os.path.abspath(__file__))
CYPHER_DIR = os.path.dirname(HERE)
PYLIB = os.path.join(HERE, ".pylib")
if os.path.isdir(PYLIB) and PYLIB not in sys.path:
    sys.path.insert(0, PYLIB)          # langfuse lives here, not in the shared venv
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(CYPHER_DIR, "harness"))
sys.path.insert(0, CYPHER_DIR)

import tracing as T                                            # noqa: E402
import harness as H                                            # noqa: E402
from score import score, score_lenient                         # noqa: E402

LEDGER = os.path.join(HERE, "ledger.csv")
CAP_USD = 1.00

# Mirrors harness/run_harness.py CONFIGS. Imported from there when possible so the two
# cannot drift; the copy is the fallback while that file is being edited.
CONFIGS = {
    "plain":           {"mode": "single", "repair": False, "gate": False},
    "repair1":         {"mode": "single", "repair": True},
    "repair1_fewshot": {"mode": "single", "repair": True, "fewshot": True},
    "prune_repair1":   {"mode": "single", "repair": True, "prune": True},
    "vote3":           {"mode": "vote", "repair": True},
    "route_big":       {"mode": "route", "repair": True},
}
try:
    import run_harness as _RH  # noqa: E402
    CONFIGS = dict(_RH.CONFIGS)
except Exception:  # noqa: BLE001  sibling may be mid-edit; the copy above still works
    pass

_call_tls = threading.local()


# ---------------------------------------------------------------- ledger
def ledger_total():
    if not os.path.exists(LEDGER):
        return 0.0
    with open(LEDGER) as f:
        return sum(float(r["cost"]) for r in csv.DictReader(f))


def ledger_add(model, tin, tout, cost, note):
    new = not os.path.exists(LEDGER)
    with open(LEDGER, "a", newline="") as f:
        w = csv.writer(f)
        if new:
            w.writerow(["timestamp", "model", "in_tokens", "out_tokens", "cost", "note"])
        w.writerow([datetime.datetime.now().isoformat(timespec="seconds"), model, tin, tout,
                    f"{cost:.6f}", note])


def new_budget():
    start = ledger_total()
    if start >= CAP_USD:
        sys.exit(f"trace ledger at ${start:.2f} >= cap ${CAP_USD:.2f}; not spending more")
    return H.Budget(start, CAP_USD)


def record_spend(budget, note):
    for m, (tin, tout, c) in budget.by_model.items():
        ledger_add(m, tin, tout, c, note)


def cost_of(model, tin, tout):
    pin, pout = H.PRICING.get(model, (0.0, 0.0))
    return (tin * pin + tout * pout) / 1e6


# ---------------------------------------------------------------- wrappers
def install():
    """Replace harness names with traced versions. Idempotent; a no-op when tracing is off."""
    if not T.ACTIVE or getattr(H, "_traced", False):
        return
    T.install_thread_propagation()

    orig_prune = H.schema_prune
    orig_validate = H.validate
    orig_exec = H._exec
    orig_call = H.call_model
    orig_attempt = H.generate_and_repair
    orig_vote = H.vote3
    orig_route = H.route

    def schema_prune(question, schema):
        with T.span("schema_prune", chars_before=len(schema or "")) as sp:
            out, applied = orig_prune(question, schema)
            sp.update(input={"question": question},
                      output={"applied": applied, "chars_after": len(out or ""),
                              "schema": out},
                      note=(f"pruned {len(schema or '')} -> {len(out or '')} chars"
                            if applied else "kept the full schema (too little survived)"))
            return out, applied

    def validate(query, schema):
        with T.span("validate") as sp:
            problems = orig_validate(query, schema)
            sp.update(input={"cypher": query},
                      output={"problems": problems, "n_problems": len(problems),
                              "unsafe": H.is_unsafe(problems)},
                      note=(f"{len(problems)} problem(s): " + "; ".join(problems)[:300])
                      if problems else "no schema problems")
            return problems

    def _exec(graph, cypher, problems):
        t0 = time.time()
        with T.span("execute", graph=graph) as sp:
            res = orig_exec(graph, cypher, problems)
            status = "error" if not res["ok"] else ("empty" if not res["rows"] else "rows")
            sp.update(input={"graph": graph, "cypher": cypher},
                      output={"status": status, "row_count": len(res["rows"]),
                              "columns": res.get("columns"), "error": res.get("error"),
                              "rows_head": res["rows"][:5]},
                      latency_s=round(res.get("secs") or (time.time() - t0), 3),
                      error=res.get("error"),
                      note=(f"{status}: {len(res['rows'])} row(s) in "
                            f"{res.get('secs', 0)}s" if res["ok"] else
                            f"failed: {str(res.get('error'))[:200]}"))
            return res

    def call_model(model, messages, budget, temperature=0.0, max_tokens=4096, reasoning="low"):
        n = getattr(_call_tls, "n", 0)
        _call_tls.n = n + 1
        name = "generate" if n == 0 else ("repair" if n == 1 else f"model_call_{n}")
        with T.span(name, kind="generation", model=model) as sp:
            r = orig_call(model, messages, budget, temperature, max_tokens, reasoning)
            cost = cost_of(model, r["in"], r["out"])
            sp.update(input=messages, output=r["raw"], model=model,
                      usage={"input": r["in"], "output": r["out"],
                             "total": r["in"] + r["out"]},
                      cost=cost,
                      metadata={"temperature": temperature, "reasoning_effort": reasoning,
                                "reasoning_tokens": r.get("reasoning"),
                                "finish_reason": r.get("finish"),
                                "latency_s": round(r["latency"], 3)},
                      error=r.get("api_error"),
                      note=(f"{model.split('/')[-1]}: {r['in']} prompt + {r['out']} completion "
                            f"tokens, ${cost:.5f}, {r['latency']:.1f}s"))
            return r

    def generate_and_repair(ex, cfg, budget, temperature=0.0, model=None, train=None):
        prev = getattr(_call_tls, "n", 0)
        _call_tls.n = 0
        m = model or cfg.get("model", H.SMALL)
        with T.span("attempt", model=m, temperature=temperature) as sp:
            try:
                rec = orig_attempt(ex, cfg, budget, temperature, model, train)
            finally:
                _call_tls.n = prev
            res = rec["result"]
            status = "error" if not res["ok"] else ("empty" if not res["rows"] else "rows")
            sp.update(input={"question": ex["question"], "graph": ex["graph"]},
                      output={"cypher": rec["cypher"], "status": status,
                              "row_count": len(res["rows"]), "rows_head": res["rows"][:5],
                              "problems": rec["problems"], "repaired": rec["repaired"]},
                      metadata={"model": m, "calls": rec["calls"], "pruned": rec["pruned"],
                                "in_tokens": rec["in"], "out_tokens": rec["out"],
                                "statuses": rec["statuses"]},
                      usage={"input": rec["in"], "output": rec["out"]},
                      cost=cost_of(m, rec["in"], rec["out"]),
                      note=(f"{m.split('/')[-1]} -> {status}, "
                            f"{'repaired once' if rec['repaired'] else 'no repair needed'}, "
                            f"{rec['calls']} model call(s)"))
            return rec

    def vote3(ex, cfg, budget, train=None):
        with T.span("vote") as sp:
            v = orig_vote(ex, cfg, budget, train)
            per = [{"attempt": i, "cypher": a["cypher"],
                    "status": ("error" if not a["result"]["ok"]
                               else "empty" if not a["result"]["rows"] else "rows"),
                    "row_count": len(a["result"]["rows"])}
                   for i, a in enumerate(v["attempts"])]
            sp.update(input={"question": ex["question"], "n_attempts": len(v["attempts"]),
                             "temperature": 0.7},
                      output={"per_attempt": per, "agreement": v["agreement"],
                              "chosen": v["chosen"]},
                      note=(f"{v['agreement']}/3 attempts agreed on the same result set; "
                            f"took attempt {v['chosen']}"))
            return v

    def route(ex, cfg, budget, train=None):
        with T.span("route") as sp:
            v = orig_route(ex, cfg, budget, train)
            big = cfg.get("big_model", H.BIG)
            sp.update(input={"question": ex["question"],
                             "escalate_below": cfg.get("escalate_below", 2)},
                      output={"escalated": v["escalated"], "agreement": v["agreement"],
                              "chosen": v["chosen"],
                              "big_model": big if v["escalated"] else None},
                      note=("escalated to " + big.split("/")[-1] if v["escalated"]
                            else "no escalation; the small model's vote was confident enough"))
            return v

    H.schema_prune, H.validate, H._exec, H.call_model = schema_prune, validate, _exec, call_model
    H.generate_and_repair, H.vote3, H.route = generate_and_repair, vote3, route
    H._traced = True


# ---------------------------------------------------------------- data helpers
def load_test():
    path = os.path.join(CYPHER_DIR, "data", "test.jsonl")
    return [json.loads(l) for l in open(path) if l.strip()]


def load_train():
    path = os.path.join(CYPHER_DIR, "data", "train.jsonl")
    if not os.path.exists(path):
        return []
    return [json.loads(l) for l in open(path) if l.strip()]


def schema_for(graph, rows=None):
    """The schema text for a graph, taken from the locked test set (read-only)."""
    for r in (rows if rows is not None else load_test()):
        if r["graph"] == graph:
            return r["schema"]
    raise SystemExit(f"unknown graph {graph!r}; known: " +
                     ", ".join(sorted({r['graph'] for r in load_test()})))


def adhoc_example(question, graph, rows=None):
    """Build a harness example dict for a question with no gold answer."""
    return {"id": "adhoc", "question": question, "graph": graph,
            "schema": schema_for(graph, rows), "cypher": "", "gold_result": None,
            "complexity": {"tier": "unknown"}}


# ---------------------------------------------------------------- one traced question
def run_one(ex, cfg, cfg_name, budget, train, session_id=None):
    """Run one question through the harness inside a root trace.

    Returns a record dict with the prediction, status, tokens, cost, latency, the local
    span tree and the Langfuse trace URL (None when Langfuse is off).
    """
    tier = (ex.get("complexity") or {}).get("tier", "unknown")
    gold = ex.get("gold_result")
    t0 = time.time()
    with T.trace("text2cypher",
                 tags=[ex["graph"], tier, cfg_name],
                 graph=ex["graph"], tier=tier, config=cfg_name, row_id=ex.get("id")) as root:
        root.update(input={"question": ex["question"], "graph": ex["graph"],
                           "config": cfg_name, "tier": tier},
                    session_id=session_id)
        if cfg["mode"] == "single":
            atts = [H.generate_and_repair(ex, cfg, budget, temperature=0.0, train=train)]
            chosen, agreement, escalated = 0, None, False
        else:
            v = (H.vote3 if cfg["mode"] == "vote" else H.route)(ex, cfg, budget, train)
            atts, chosen, agreement = v["attempts"], v["chosen"], v["agreement"]
            escalated = v.get("escalated", False)
        final = atts[chosen]
        res = final["result"]
        status = "error" if not res["ok"] else ("empty" if not res["rows"] else "rows")

        correct = lenient = None
        if gold:
            g = {"ok": True, **gold}
            correct = score(g, res, ex["cypher"]) == "correct"
            lenient = score_lenient(g, res, ex["cypher"]) == "correct"

        tin = sum(a["in"] for a in atts)
        tout = sum(a["out"] for a in atts)
        cost = sum(cost_of(a["model"], a["in"], a["out"]) for a in atts)
        latency = round(time.time() - t0, 3)

        root.update(output={"cypher": final["cypher"], "status": status,
                            "row_count": len(res["rows"]), "rows": res["rows"][:50],
                            "columns": res.get("columns"), "error": res.get("error"),
                            **({"correct": correct, "correct_lenient": lenient,
                                "gold_cypher": ex["cypher"]} if gold else {})},
                    metadata={"agreement": agreement, "escalated": escalated,
                              "in_tokens": tin, "out_tokens": tout,
                              "cost_usd": round(cost, 6), "latency_s": latency,
                              "model_calls": sum(a["calls"] for a in atts)},
                    usage={"input": tin, "output": tout}, cost=cost)
        if correct is not None:
            root.score("correct", 1 if correct else 0, data_type="NUMERIC",
                       comment=f"execution-equality vs gold ({ex.get('id')})")
            root.score("correct_lenient", 1 if lenient else 0, data_type="NUMERIC")
        root.score("latency_s", latency, data_type="NUMERIC")
        root.score("cost_usd", round(cost, 6), data_type="NUMERIC")

        url = root.url

    return {"id": ex.get("id"), "graph": ex["graph"], "tier": tier, "question": ex["question"],
            "cypher": final["cypher"], "status": status, "row_count": len(res["rows"]),
            "rows": res["rows"], "columns": res.get("columns"), "error": res.get("error"),
            "correct": correct, "correct_lenient": lenient, "agreement": agreement,
            "escalated": escalated, "in_tokens": tin, "out_tokens": tout,
            "cost_usd": round(cost, 6), "latency_s": latency,
            "model_calls": sum(a["calls"] for a in atts),
            "trace_url": url, "tree": T.last_tree()}


def status_line():
    """One line saying which switches are on."""
    parts = [f"langfuse={'on' if T.LANGFUSE_ON else 'off'}",
             f"local_json={'on' if T.LOCAL_ON else 'off'}"]
    if T.LANGFUSE_ON:
        parts.append(f"host={os.environ.get('LANGFUSE_HOST', 'https://cloud.langfuse.com')}")
    return "tracing: " + "  ".join(parts)
