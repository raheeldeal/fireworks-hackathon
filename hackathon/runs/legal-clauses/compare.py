#!/usr/bin/env python3
"""Side-by-side table of result files (adapted from hackathon/eval/compare.py; adds macro-F1). Skips smoke_*."""
import glob, json, os, sys
paths = sys.argv[1:] or sorted(p for p in glob.glob(os.path.join(os.path.dirname(__file__), "results", "*.json"))
                               if not os.path.basename(p).startswith(("smoke_", "dev_")))
runs = [json.load(open(p)) for p in paths]
print(f"{'run':62s} {'n':>4s} {'acc':>6s} {'mF1':>6s} {'inval':>5s} {'p50 s':>6s} {'p95 s':>6s} {'$/1k':>8s}")
print("-" * 110)
for r in runs:
    name = f"{r['model'].split('/')[-1]} + {r['prompt']} {r.get('tag','')} s{r.get('seed','')}"
    print(f"{name:62s} {r['n']:4d} {r['accuracy']:6.1%} {r.get('macro_f1',0):6.3f} {r['invalid_outputs']:5d} {r['p50_latency_s']:6.2f} {r['p95_latency_s']:6.2f} {r['cost_per_1k_requests_usd']:8.4f}")
