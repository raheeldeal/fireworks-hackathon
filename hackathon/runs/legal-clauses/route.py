#!/usr/bin/env python3
"""Simulate small->large routing from two existing result files (same test set, same ids).
Escalate when the small model's answer is invalid or its confidence (first-token prob) is below a threshold.
  python3 route.py results/<small>.json results/<large>.json --thresholds 0.5 0.7 0.9 0.95
Writes results/route_<small>_to_<large>_t<thr>.json per threshold in the shared result shape."""
import argparse, json, os, statistics
import score
HERE = os.path.dirname(os.path.abspath(__file__))
ap = argparse.ArgumentParser()
ap.add_argument("small"); ap.add_argument("large")
ap.add_argument("--thresholds", type=float, nargs="+", default=[0.5, 0.7, 0.9])
a = ap.parse_args()
S, L = json.load(open(a.small)), json.load(open(a.large))
lrows = {r["id"]: r for r in L["rows"]}
cs, cl = S["cost_usd"] / S["n"], L["cost_usd"] / L["n"]   # per-request cost of each model
print(f"{'threshold':>9s} {'acc':>6s} {'macroF1':>8s} {'escalated':>9s} {'$/1k':>8s} {'p50':>6s} {'p95':>6s}")
for t in a.thresholds:
    rows, cost = [], 0.0
    for r in S["rows"]:
        if r["id"] not in lrows:
            continue
        conf = r["confidence"] if r["confidence"] is not None else 1.0
        esc = r["pred"] == "invalid" or conf < t
        src = lrows[r["id"]] if esc else r
        rows.append({**src, "escalated": esc, "latency": r["latency"] + (lrows[r["id"]]["latency"] if esc else 0)})
        cost += cs + (cl if esc else 0)
    m = score.metrics(rows); lat = sorted(x["latency"] for x in rows); n = len(rows)
    out = {"model": f"route({S['model'].split('/')[-1]}->{L['model'].split('/')[-1]})", "prompt": S["prompt"], "tag": f"t{t}",
           "seed": S["seed"], "mock": False, "n": n, "accuracy": m["accuracy"], "macro_f1": m["macro_f1"], "invalid_outputs": m["invalid"],
           "p50_latency_s": round(statistics.median(lat), 3), "p95_latency_s": round(lat[int(0.95 * (n - 1))], 3),
           "escalated": sum(r["escalated"] for r in rows), "cost_usd": round(cost, 4),
           "cost_per_1k_requests_usd": round(cost / n * 1000, 4), "rows": rows}
    p = os.path.join(HERE, "results", f"route_{S['model'].split('/')[-1]}_to_{L['model'].split('/')[-1]}_t{t}.json")
    json.dump(out, open(p, "w"), indent=1)
    print(f"{t:9.2f} {m['accuracy']:6.1%} {m['macro_f1']:8.3f} {out['escalated']:9d} {out['cost_per_1k_requests_usd']:8.3f} {out['p50_latency_s']:6.2f} {out['p95_latency_s']:6.2f}")
