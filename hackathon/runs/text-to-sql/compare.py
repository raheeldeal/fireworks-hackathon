#!/usr/bin/env python3
"""Side-by-side table of results files (text-to-SQL version of hackathon/eval/compare.py)."""
import glob, json, os, sys
paths = sys.argv[1:] or sorted(glob.glob(os.path.join(os.path.dirname(os.path.abspath(__file__)), "results", "*.json")))
runs = [json.load(open(p)) for p in paths]
print(f"{'run':52s} {'exec':>6s} {'exact':>6s} {'inval':>5s} {'p50 s':>6s} {'p95 s':>6s} {'$/1k':>8s} {'n':>4s}")
print("-" * 100)
for r in runs:
    name = f"{r['model'].split('/')[-1]} + {r['prompt']}" + (f" s{r.get('seed')}" if r.get('seed') else "")
    print(f"{name:52s} {r['accuracy']:6.1%} {r.get('exact_match',0):6.1%} {r['invalid_outputs']:5d} {r['p50_latency_s']:6.2f} {r['p95_latency_s']:6.2f} {r['cost_per_1k_requests_usd']:8.4f} {r['n']:4d}")
if "--misses" in os.environ.get("SHOW", "") or len(sys.argv) == 2:
    best = runs[-1]
    for m in [x for x in best["rows"] if not x["correct"]][:40]:
        print(f"\n[{m['db_id']}] {m['question']}\n  gold: {m['gold_sql']}\n  pred: {m['pred_sql'][:300]}\n  err : {m['error']}")
