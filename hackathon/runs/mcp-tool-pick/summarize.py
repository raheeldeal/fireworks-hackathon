#!/usr/bin/env python3
"""Print the RESULTS.md table from results/*.json (groups seeds of the same model+tag: mean ± range)."""
import json, glob, collections, os, sys
HERE = os.path.dirname(os.path.abspath(__file__))
paths = sys.argv[1:] or sorted(glob.glob(os.path.join(HERE, "results", "*.json")))
groups = collections.defaultdict(list)
for p in paths:
    d = json.load(open(p)); groups[(d["model"], d.get("tag", d["prompt"]))].append(d)
print("| config | model | accuracy | top-3 | invalid | p50 s | p95 s | $/1k | catalog % of cost | seeds |")
print("|---|---|---|---|---|---|---|---|---|---|")
def fmt(vals, pct=True):
    m = sum(vals) / len(vals)
    s = f"{m:.1%}" if pct else f"{m:.4f}"
    if len(vals) > 1:
        rng = (max(vals) - min(vals)) / 2
        s += f" ± {rng:.1%}" if pct else f" ± {rng:.4f}"
    return s
for (model, tag), ds in sorted(groups.items(), key=lambda kv: (-max(d["accuracy"] for d in kv[1]))):
    d0 = ds[0]
    top3 = fmt([d.get("top3_accuracy", d["accuracy"]) for d in ds]) if "top3_accuracy" in d0 else "-"
    cat = f"{d0['catalog_cost_share']:.0%}" if d0.get("catalog_cost_share") is not None else "-"
    extra = f" (n={d0['n']})" if d0["n"] != 180 else ""
    print(f"| {tag}{extra} | {model.split('/')[-1]} | {fmt([d['accuracy'] for d in ds])} | {top3} | {sum(d['invalid_outputs'] for d in ds)/len(ds):.1f} | {sum(d['p50_latency_s'] for d in ds)/len(ds):.2f} | {sum(d['p95_latency_s'] for d in ds)/len(ds):.2f} | {fmt([d['cost_per_1k_requests_usd'] for d in ds], False)} | {cat} | {len(ds)} |")
