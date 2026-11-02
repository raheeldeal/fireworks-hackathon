#!/usr/bin/env python3
"""Side-by-side table of results files (first = baseline)."""
import glob, json, os, sys
paths = sys.argv[1:] or sorted(glob.glob(os.path.join(os.path.dirname(__file__), "results", "*.json")))
runs = [json.load(open(p)) for p in paths]
b = runs[0]
print(f"{'run':44s} {'n':>4s} {'F1':>6s} {'ΔF1':>6s} {'P':>6s} {'R':>6s} {'due':>6s} {'inv':>4s} {'p50':>6s} {'p95':>6s} {'$/1k':>8s}")
print("-" * 112)
for r in runs:
    name = f"{r['model'].split('/')[-1]} + {r['prompt']}" + (f" s{r['seed']}" if r.get('seed') else "")
    print(f"{name:44s} {r['n']:4d} {r['f1']:6.3f} {r['f1']-b['f1']:+6.3f} {r['precision']:6.3f} {r['recall']:6.3f} {r['due_acc']:6.3f} {r['invalid_outputs']:4d} {r['p50_latency_s']:6.2f} {r['p95_latency_s']:6.2f} {r['cost_per_1k_requests_usd']:8.3f}")
