#!/usr/bin/env python3
"""Side-by-side table of results files (F1 = accuracy column, plus exact-set accuracy)."""
import glob, json, os, sys
paths = sys.argv[1:] or sorted(glob.glob(os.path.join(os.path.dirname(os.path.abspath(__file__)), "results", "*.json")))
runs = [json.load(open(p)) for p in paths]
print(f"{'run':46s} {'n':>4s} {'F1':>6s} {'exact':>6s} {'inval':>5s} {'p50 s':>6s} {'p95 s':>6s} {'$/1k':>7s}")
print("-" * 92)
for r in runs:
    name = f"{r['model'].split('/')[-1]} + {r['prompt']} s{r.get('seed','')}"
    print(f"{name:46s} {r['n']:4d} {r['accuracy']:6.3f} {r.get('exact_accuracy',0):6.3f} {r['invalid_outputs']:5d} {r['p50_latency_s']:6.2f} {r['p95_latency_s']:6.2f} {r['cost_per_1k_requests_usd']:7.3f}")
