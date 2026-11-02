#!/usr/bin/env python3
"""Print a side-by-side table of every results file. This table IS your submission."""
import glob
import json
import os
import sys

paths = sys.argv[1:] or sorted(glob.glob(os.path.join(os.path.dirname(__file__), "results", "*.json")))
if not paths:
    sys.exit("no results yet; run run_eval.py first")

runs = [json.load(open(p)) for p in paths]
baseline = runs[0]

print(f"{'run':38s} {'acc':>6s} {'Δ acc':>7s} {'invalid':>7s} {'p50 s':>6s} {'p95 s':>6s} {'$/1k':>8s} {'Δ cost':>7s}")
print("-" * 92)
for r in runs:
    name = f"{r['model'].split('/')[-1]} + {r['prompt']}"
    d_acc = r["accuracy"] - baseline["accuracy"]
    base_cost = baseline["cost_per_1k_requests_usd"] or 1e-9
    d_cost = (r["cost_per_1k_requests_usd"] / base_cost - 1) * 100
    print(f"{name:38s} {r['accuracy']:6.1%} {d_acc:+7.1%} {r['invalid_outputs']:7d} {r['p50_latency_s']:6.2f} {r['p95_latency_s']:6.2f} {r['cost_per_1k_requests_usd']:8.4f} {d_cost:+6.0f}%")

print("\nfirst row is the baseline. Δ columns are relative to it." + ("  (MOCK DATA)" if any(r["mock"] for r in runs) else ""))

# Show where the best run still fails: these drive your next prompt edit or training examples.
best = max(runs, key=lambda r: r["accuracy"])
misses = [row for row in best["rows"] if not row["correct"]]
if misses:
    print(f"\nmisses for best run ({best['model'].split('/')[-1]} + {best['prompt']}):")
    for m in misses:
        print(f"  {m['label']:16s} predicted {m['pred']:16s} | {m['text'][:70]}")
