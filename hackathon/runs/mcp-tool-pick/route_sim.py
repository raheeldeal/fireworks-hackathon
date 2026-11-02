#!/usr/bin/env python3
"""Offline routing simulation: small model answers; escalate to the large model when first-token logprob < threshold.
Both result files must cover the same rows at temperature 0, so the simulation is exact (no extra calls).
Usage: python3 route_sim.py results/<small>.json results/<large>.json [--thresholds -0.05 -0.2 -0.5 -1.0] [--out results/route_X.json]"""
import json, sys, argparse, statistics, os
import fw
ap = argparse.ArgumentParser(); ap.add_argument("small"); ap.add_argument("large")
ap.add_argument("--thresholds", type=float, nargs="+", default=[-0.02, -0.05, -0.1, -0.2, -0.5, -1.0]); ap.add_argument("--out")
a = ap.parse_args()
S, L = json.load(open(a.small)), json.load(open(a.large))
lrows = {r["id"]: r for r in L["rows"]}
ps = fw.PRICING[S["model"]]; pl = fw.PRICING[L["model"]]
def cost(r, p): return (r["in_tokens"] * p[0] + r["out_tokens"] * p[1]) / 1e6
out = []
for t in a.thresholds:
    rows, lat, c, esc = [], [], 0.0, 0
    for r in S["rows"]:
        if r["id"] not in lrows: continue
        lp = r.get("first_token_logprob"); conf_low = (lp is None) or (lp < t) or r["pred"] == "invalid"
        c += cost(r, ps); l = r["latency"]; pred = r["pred"]
        if conf_low:
            esc += 1; lr = lrows[r["id"]]; c += cost(lr, pl); l += lr["latency"]; pred = lr["pred"]
        rows.append({"id": r["id"], "label": r["label"], "pred": pred, "correct": pred == r["label"], "escalated": conf_low, "latency": l})
        lat.append(l)
    n = len(rows); lat.sort()
    summ = {"model": f"route({S['model'].split('/')[-1]}->{L['model'].split('/')[-1]})", "prompt": f"{S['prompt']}+route@{t}", "tag": f"route@{t}", "n": n, "seed": S.get("seed", 0),
            "threshold": t, "escalation_rate": round(esc / n, 3), "accuracy": round(sum(r["correct"] for r in rows) / n, 4),
            "invalid_outputs": sum(r["pred"] == "invalid" for r in rows), "p50_latency_s": round(statistics.median(lat), 3),
            "p95_latency_s": round(lat[int(0.95 * (n - 1))], 3), "cost_per_1k_requests_usd": round(c / n * 1000, 4), "rows": rows}
    out.append(summ)
    print(f"t={t:6.2f} escalate {summ['escalation_rate']:.0%}  acc {summ['accuracy']:.3f}  p50 {summ['p50_latency_s']}s  ${summ['cost_per_1k_requests_usd']:.4f}/1k")
if a.out:
    base = a.out[:-5] if a.out.endswith(".json") else a.out
    for s in out:
        json.dump(s, open(f"{base}@{s['threshold']}.json", "w"), indent=1)
