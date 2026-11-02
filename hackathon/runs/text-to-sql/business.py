#!/usr/bin/env python3
"""Monthly cost and error counts per configuration at the SPEC.md workload (50,000 questions/day)."""
import glob, json, os, sys
HERE = os.path.dirname(os.path.abspath(__file__))
CALLS_PER_DAY = 50_000; DAYS = 30
paths = sys.argv[1:] or sorted(glob.glob(os.path.join(HERE, "results", "*.json")))
runs = [json.load(open(p)) for p in paths if "seed" not in os.path.basename(p) and "sft_job" not in p]
print(f"Workload: {CALLS_PER_DAY:,} questions/day, {CALLS_PER_DAY*DAYS:,}/month\n")
print(f"| config | accuracy | $/1k | $/month | wrong answers/month | analyst hours/month (10 min each) |")
print("|---|---|---|---|---|---|")
for r in sorted(runs, key=lambda r: -r["accuracy"]):
    name = f"{r['model'].split('/')[-1]} + {r['prompt']}"
    monthly = r["cost_per_1k_requests_usd"] / 1000 * CALLS_PER_DAY * DAYS
    wrong = (1 - r["accuracy"]) * CALLS_PER_DAY * DAYS
    print(f"| {name} | {r['accuracy']:.1%} | ${r['cost_per_1k_requests_usd']:.3f} | ${monthly:,.0f} | {wrong:,.0f} | {wrong/6:,.0f} |")
