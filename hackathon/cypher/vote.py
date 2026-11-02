"""Cross-model voting by execution: pick the answer whose result rows most models agree on.

  python vote.py results/dev_r5w.json results/dev_teacher_gpt-oss-120b.json results/dev_teacher_glm-5p3.json
  python vote.py --tag r14_vote results/r5_full.json results/r13_gptoss.json:repair results/r15_glm.json   # writes a result file

Each argument is a result file, optionally read at a stage (file.json:stage, see compare.py). For every question the
final query of each run is re-executed (cached; no model calls), and candidates are grouped by their result rows,
compared the same way score.py compares rows. The biggest group wins; ties go to the earlier file. Queries that error
or return nothing get no vote. Gold is used only afterwards, to grade the pick.

Cost per question = the sum over runs (every model is called); latency = the slowest run (models run in parallel).
"""
import argparse, json, os, statistics
from collections import Counter
from concurrent.futures import ThreadPoolExecutor

import metrics
from executor import execute
from score import row_key, score

HERE = os.path.dirname(os.path.abspath(__file__))


def fingerprint(res):
    """Order-free, column-name-free signature of a result set; None if it errored or is empty."""
    if not res["ok"] or not res["rows"]:
        return None
    return tuple(sorted(Counter(row_key(r, res["columns"], False) for r in res["rows"]).items(), key=repr))


def load(spec):
    path, _, stage = spec.partition(":")
    doc = json.load(open(path))
    return doc, stage or list(doc["views"])[-1]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("runs", nargs="+")
    ap.add_argument("--data", help="question file with gold (default: the first run's data)")
    ap.add_argument("--tag", help="also write results/<tag>.json in run_eval's shape, for the dashboard")
    args = ap.parse_args()

    runs = [load(s) for s in args.runs]
    data = args.data or os.path.join(HERE, runs[0][0]["data"])
    gold = {r["id"]: r for r in (json.loads(l) for l in open(data))}
    by_run = [{r["id"]: (r, metrics.cut(r, stage)) for r in doc["rows"]} for doc, stage in runs]
    ids = sorted(set.intersection(*(set(b) for b in by_run)))

    # every distinct (graph, query) once
    queries = {(gold[i]["graph"], b[i][1].get("cypher")) for i in ids for b in by_run if b[i][1].get("cypher")}
    with ThreadPoolExecutor(8) as ex:
        results = dict(zip(queries, ex.map(lambda q: execute(*q), queries)))

    rows, oracle = [], 0
    for i in ids:
        g = gold[i]
        cands = []
        for k, b in enumerate(by_run):
            q = b[i][1].get("cypher")
            res = results.get((g["graph"], q)) if q else None
            cands.append((k, q, res, fingerprint(res) if res else None))
        votes = Counter(fp for _, _, _, fp in cands if fp is not None)
        if votes:
            top = max(votes.values())
            winner = next(c for c in cands if c[3] is not None and votes[c[3]] == top)  # earliest file breaks ties
        else:
            winner = cands[0]  # nobody returned rows: fall back to the first run's answer
        gold_res = g.get("gold_result") or execute(g["graph"], g["cypher"])
        grade = lambda c: score(gold_res, c[2], g["cypher"]) if c[2] else "error"
        outcome = grade(winner)
        oracle += any(grade(c) == "correct" for c in cands)
        cuts = [b[i][1] for b in by_run]
        rows.append({"id": i, "graph": g["graph"], "tier": g["complexity"]["tier"], "question": g["question"],
                     "gold_cypher": g["cypher"], "final_cypher": winner[1], "outcome": outcome, "stage": "first",
                     "votes": votes[winner[3]] if winner[3] else 0, "winner_run": winner[0],
                     "examples": [], "langfuse_trace_id": by_run[winner[0]][i][0].get("langfuse_trace_id"),
                     # one synthetic attempt so metrics/dashboard can read this file like any other run
                     "attempts": [{"source": "first", "model": "vote", "cypher": winner[1], "status": "rows",
                                   "outcome": outcome, "n_rows": len(winner[2]["rows"]) if winner[2] else 0,
                                   "error": None, "warnings": [], "calls": sum(c["calls"] for c in cuts),
                                   "cost": sum(c["cost"] for c in cuts), "secs": max(c["secs"] for c in cuts),
                                   "in_tokens": 0, "out_tokens": 0}]})

    s = metrics.summarize(rows, "first")
    names = [f"{doc['tag']}:{stage}" for doc, stage in runs]
    for (doc, stage), name in zip(runs, names):
        single = metrics.summarize(doc["rows"], stage)
        print(f"  {name:<34} {single['accuracy']:.1%}   ${single['cost_per_question']:.5f}/q")
    print(f"VOTE over {len(runs)} runs: {s['accuracy']:.1%}  CI {s['ci95']}  ${s['cost_per_question']:.5f}/q  "
          f"p50 {s['p50_secs']:.2f}s   oracle (any run right) {oracle / len(ids):.1%}   n={len(ids)}")
    print("  winner by run:", dict(Counter(names[r["winner_run"]] for r in rows)))
    if args.tag:
        doc = {"tag": args.tag, "split": runs[0][0]["split"], "data": runs[0][0]["data"], "model": "vote: " + ", ".join(names),
               "escalate_model": None, "config": {"vote": names}, "summary": s, "views": {"first": s}, "rows": rows}
        path = os.path.join(HERE, "results", f"{args.tag}.json")
        json.dump(doc, open(path, "w"), indent=1, default=str)
        print("wrote", os.path.relpath(path, HERE))


if __name__ == "__main__":
    main()
