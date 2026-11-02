#!/usr/bin/env python3
"""Side-by-side table of result files (markdown). Usage: python3 compare.py results/*.json"""
import glob, json, os, sys
paths = sys.argv[1:] or sorted(glob.glob(os.path.join(os.path.dirname(__file__), "results", "*.json")))
runs = [json.load(open(p)) for p in paths]
print("| config | model | accuracy (all fields) | field mean | invalid | p50 s | p95 s | $/1k | n |")
print("|---|---|---|---|---|---|---|---|---|")
for r in sorted(runs, key=lambda r: r["cost_per_1k_requests_usd"]):
    print(f"| {r['prompt']} | {r['model'].split('/')[-1]} | {r['accuracy']:.1%} | {r.get('mean_field_accuracy',0):.1%} | {r['invalid_outputs']} | {r['p50_latency_s']:.2f} | {r['p95_latency_s']:.2f} | {r['cost_per_1k_requests_usd']:.3f} | {r['n']} |")
if runs and "field_accuracy" in runs[0]:
    print("\nPer-field accuracy:")
    keys = list(runs[0]["field_accuracy"])
    print("| config | model | " + " | ".join(keys) + " |"); print("|---|---|" + "---|" * len(keys))
    for r in runs:
        if "field_accuracy" in r:
            print(f"| {r['prompt']} | {r['model'].split('/')[-1]} | " + " | ".join(f"{r['field_accuracy'][k]:.0%}" for k in keys) + " |")
