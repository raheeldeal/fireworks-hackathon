#!/usr/bin/env python3
"""Coverage-accuracy curve recomputed from the v2 verdicts on the pooled vote runs."""
import glob, json, os, collections
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
runs = [json.load(open(p)) for p in sorted(glob.glob(os.path.join(ROOT, "results_v2", "harness_vote3*.json")))]
by = collections.defaultdict(list)
for d in runs:
    for r in d["rows"]:
        if r.get("agreement") is not None:
            by[r["agreement"]].append((bool(r["correct_v2"]), bool(r["correct_v1"])))
total = sum(len(v) for v in by.values())
out, cum = [], [0, 0, 0]
print(f"{'policy':34s} {'coverage':>9s} {'prec v1':>8s} {'prec v2':>8s}")
for a in sorted(by, key=lambda a: -a):
    v = by[a]
    cum[0] += len(v); cum[1] += sum(x[0] for x in v); cum[2] += sum(x[1] for x in v)
    cov, p2, p1 = cum[0] / total, cum[1] / cum[0], cum[2] / cum[0]
    label = {3: "answer only if 3/3 agree", 2: "answer if >=2/3 agree"}.get(a, "answer everything")
    print(f"{label:34s} {cov:9.1%} {p1:8.1%} {p2:8.1%}")
    out.append({"policy": label, "coverage": round(cov, 4), "precision_v1": round(p1, 4),
                "precision_v2": round(p2, 4), "n_row_runs": cum[0], "runs_pooled": len(runs)})
json.dump(out, open(os.path.join(ROOT, "results_v2", "coverage_curve.json"), "w"), indent=2)
print(f"\npooled {len(runs)} vote runs, {total} row-runs -> results_v2/coverage_curve.json")
