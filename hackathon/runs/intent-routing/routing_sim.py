#!/usr/bin/env python3
"""Simulate confidence routing offline. small = results json with per-row confidence; big = results json for escalation model.
Escalate when small pred is invalid or confidence < threshold. Exact under temperature 0 (same calls already made).
  python3 routing_sim.py results/small.json results/big.json [--thresholds 0.5,0.6,0.7,0.8,0.9] [--out results/routing_x.json]"""
import argparse, json, statistics
ap = argparse.ArgumentParser(); ap.add_argument("small"); ap.add_argument("big")
ap.add_argument("--thresholds", default="0.5,0.6,0.7,0.8,0.9,0.95,1.01"); ap.add_argument("--out")
a = ap.parse_args()
S, B = json.load(open(a.small)), json.load(open(a.big))
brow = {r["id"]: r for r in B["rows"]}
ids = [r["id"] for r in S["rows"] if r["id"] in brow]
sc, bc = S["cost_per_1k_requests_usd"], B["cost_per_1k_requests_usd"]
out = []
print(f"small={S['model'].split('/')[-1]}+{S['prompt']} ({S['accuracy']:.1%}, ${sc:.3f}/1k)  big={B['model'].split('/')[-1]}+{B['prompt']} ({B['accuracy']:.1%}, ${bc:.3f}/1k)  n={len(ids)}")
print(f"{'thr':>5s} {'escalated':>9s} {'accuracy':>8s} {'$/1k':>7s} {'p50 s':>6s} {'p95 s':>6s}")
for t in [float(x) for x in a.thresholds.split(",")]:
    corr, esc, lats, cost = 0, 0, [], 0.0
    for r in (x for x in S["rows"] if x["id"] in brow):
        c = r["confidence"] if r["confidence"] is not None else 0.0
        if r["pred"] == "invalid" or c < t:
            esc += 1; b = brow[r["id"]]; corr += b["correct"]; lats.append(r["latency"] + b["latency"])
            cost += (sc + bc) / 1000
        else:
            corr += r["correct"]; lats.append(r["latency"]); cost += sc / 1000
    n = len(ids); lats.sort()
    row = {"threshold": t, "escalated_frac": round(esc / n, 3), "accuracy": round(corr / n, 4),
           "cost_per_1k_requests_usd": round(cost / n * 1000, 4),
           "p50_latency_s": round(statistics.median(lats), 3), "p95_latency_s": round(lats[int(0.95 * (n - 1))], 3)}
    out.append(row)
    print(f"{t:5.2f} {row['escalated_frac']:9.1%} {row['accuracy']:8.1%} {row['cost_per_1k_requests_usd']:7.3f} {row['p50_latency_s']:6.2f} {row['p95_latency_s']:6.2f}")
if a.out:
    json.dump({"small": a.small, "big": a.big, "n": len(ids), "sweep": out}, open(a.out, "w"), indent=2); print("saved", a.out)
