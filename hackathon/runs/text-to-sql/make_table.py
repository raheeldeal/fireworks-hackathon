#!/usr/bin/env python3
"""Markdown results table for RESULTS.md. Seed runs of the same config are pooled into mean ± half-range."""
import glob, json, os, re, statistics
HERE = os.path.dirname(os.path.abspath(__file__))
groups = {}
for p in sorted(glob.glob(os.path.join(HERE, "results", "*.json"))):
    b = os.path.basename(p)
    if b.startswith(("scratch", "sft_job")) or (b.startswith("route_") and not re.search(r"th-(1\.0|0\.1)\.json$", b)):
        continue
    d = json.load(open(p))
    key = re.sub(r"_seed\d+", "", b[:-5])
    groups.setdefault(key, []).append(d)
rows = []
for key, ds in groups.items():
    d0 = ds[0]; accs = [d["accuracy"] for d in ds]
    acc = f"{statistics.mean(accs):.1%}" + (f" ± {(max(accs)-min(accs))/2:.1%}" if len(ds) > 1 else "")
    lenient = [d.get("lenient_accuracy") for d in ds if d.get("lenient_accuracy") is not None]
    rows.append((statistics.mean(accs), f"| {d0['prompt']} | {d0['model'].split('/')[-1]} | {acc} | "
        f"{statistics.mean(d['invalid_outputs'] for d in ds):.0f} | {statistics.mean(d['p50_latency_s'] for d in ds):.2f} | "
        f"{statistics.mean(d['p95_latency_s'] for d in ds):.2f} | {statistics.mean(d['cost_per_1k_requests_usd'] for d in ds):.3f} | {len(ds)} | "
        f"{statistics.mean(lenient):.1%} | {d0['n']} |" if lenient else
        f"| {d0['prompt']} | {d0['model'].split('/')[-1]} | {acc} | {statistics.mean(d['invalid_outputs'] for d in ds):.0f} | "
        f"{statistics.mean(d['p50_latency_s'] for d in ds):.2f} | {statistics.mean(d['p95_latency_s'] for d in ds):.2f} | "
        f"{statistics.mean(d['cost_per_1k_requests_usd'] for d in ds):.3f} | {len(ds)} | n/a | {d0['n']} |"))
print("| config | model | accuracy (exec) | invalid | p50 s | p95 s | $/1k | seeds | lenient exec | n |")
print("|---|---|---|---|---|---|---|---|---|---|")
for _, line in sorted(rows, key=lambda x: -x[0]):
    print(line)
