#!/usr/bin/env python3
"""Aggregate seed runs of one config into mean ± range. Usage: python3 variance.py results/glm-5p3-flash_v1_plain*.json"""
import json, sys, statistics
runs = [json.load(open(p)) for p in sys.argv[1:]]
acc = [r["accuracy"] for r in runs]
m = statistics.mean(acc)
print(f"{runs[0]['model'].split('/')[-1]} + {runs[0]['prompt']}: {len(runs)} seeds, accuracy mean {m:.1%}, range {min(acc):.1%}..{max(acc):.1%} (±{(max(acc)-min(acc))/2:.1%}); seeds={[r['seed'] for r in runs]}")
agg = {**runs[0], "seeds": len(runs), "accuracy": round(m, 4), "accuracy_min": min(acc), "accuracy_max": max(acc),
       "invalid_outputs": round(statistics.mean(r["invalid_outputs"] for r in runs), 1),
       "p50_latency_s": round(statistics.mean(r["p50_latency_s"] for r in runs), 3),
       "p95_latency_s": round(statistics.mean(r["p95_latency_s"] for r in runs), 3),
       "cost_per_1k_requests_usd": round(statistics.mean(r["cost_per_1k_requests_usd"] for r in runs), 4), "rows": []}
out = sys.argv[1].rsplit("_seed", 1)[0].replace(".json", "") + "_3seeds.json" if "_seed" in sys.argv[1] else sys.argv[1].replace(".json", "_3seeds.json")
json.dump(agg, open(out, "w"), indent=2); print("saved", out)
