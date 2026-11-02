#!/usr/bin/env python3
"""Side-by-side table of every results file (adapted from hackathon/eval/compare.py; adds soft score).
    venv/bin/python compare.py [results/*.json]   (default: all non-smoke, non-seed files, sorted by cost)
    venv/bin/python compare.py --md               (markdown table for RESULTS.md)
"""
import glob
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
md = "--md" in sys.argv
paths = [p for p in sys.argv[1:] if not p.startswith("--")] or sorted(glob.glob(os.path.join(HERE, "results", "*.json")))
paths = [p for p in paths if os.path.basename(p) not in ("sft_checkpoint.json",)]
if not [p for p in sys.argv[1:] if not p.startswith("--")]:  # default listing: main runs only (seed re-runs and held-out checks are reported separately)
    paths = [p for p in paths if "_seed" not in os.path.basename(p) and not os.path.basename(p).startswith("heldout_")]
runs = []
for p in paths:
    try:
        r = json.load(open(p))
    except Exception:
        continue
    if "accuracy" in r:
        r["_file"] = os.path.basename(p)
        runs.append(r)
if not runs:
    sys.exit("no results yet")
runs.sort(key=lambda r: (r["cost_per_1k_requests_usd"], -r["accuracy"]))

if md:
    print("| config | model | accuracy | soft | invalid | p50 s | p95 s | $/1k | seeds |")
    print("|---|---|---|---|---|---|---|---|---|")
    for r in runs:
        print(f"| {r['prompt']} | {r['model'].split('/')[-1]} | {r['accuracy']:.1%} | {r.get('soft_score', 0):.3f} | {r['invalid_outputs']} | "
              f"{r['p50_latency_s']:.2f} | {r['p95_latency_s']:.2f} | {r['cost_per_1k_requests_usd']:.4f} | {r.get('seeds', 1)} |")
else:
    print(f"{'file':52s} {'acc':>6s} {'soft':>6s} {'inv':>4s} {'p50':>6s} {'p95':>6s} {'$/1k':>8s} {'n':>4s}")
    print("-" * 100)
    for r in runs:
        print(f"{r['_file'][:52]:52s} {r['accuracy']:6.1%} {r.get('soft_score', 0):6.3f} {r['invalid_outputs']:4d} "
              f"{r['p50_latency_s']:6.2f} {r['p95_latency_s']:6.2f} {r['cost_per_1k_requests_usd']:8.4f} {r['n']:4d}")
