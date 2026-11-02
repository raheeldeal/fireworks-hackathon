#!/usr/bin/env python3
"""Side-by-side table of results files (same shape as hackathon/eval/compare.py, plus a markdown mode).
Usage: python3 compare.py [--md] [results/*.json ...]   (default: all results/*.json, routing files included)"""
import glob, json, os, sys

md = "--md" in sys.argv
paths = [a for a in sys.argv[1:] if not a.startswith("--")] or sorted(glob.glob(os.path.join(os.path.dirname(__file__), "results", "*.json")))
runs = [json.load(open(p)) for p in paths]
if not runs:
    sys.exit("no results yet")
if md:
    print("| config | model | accuracy | invalid | p50 s | p95 s | $/1k | seeds |")
    print("|---|---|---|---|---|---|---|---|")
    for r in runs:
        print(f"| {r['prompt']} | {r['model'].split('/')[-1]} | {r['accuracy']:.1%} | {r['invalid_outputs']} | {r['p50_latency_s']:.2f} | {r['p95_latency_s']:.2f} | {r['cost_per_1k_requests_usd']:.3f} | {r.get('seeds', 1)} |")
else:
    base = runs[0]
    print(f"{'run':50s} {'n':>4s} {'acc':>6s} {'Δacc':>6s} {'inv':>4s} {'p50':>6s} {'p95':>6s} {'$/1k':>7s}")
    print("-" * 95)
    for r in runs:
        print(f"{r['model'].split('/')[-1] + ' + ' + r['prompt']:50s} {r['n']:4d} {r['accuracy']:6.1%} {r['accuracy']-base['accuracy']:+6.1%} {r['invalid_outputs']:4d} {r['p50_latency_s']:6.2f} {r['p95_latency_s']:6.2f} {r['cost_per_1k_requests_usd']:7.3f}")
