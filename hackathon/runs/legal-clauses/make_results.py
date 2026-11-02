#!/usr/bin/env python3
"""Assemble the RESULTS.md results table (seeds grouped, mean ± range) and the misses list for the best small config.
Prints markdown to stdout; RESULTS.md is written by hand around it."""
import csv, glob, json, os, collections
HERE = os.path.dirname(os.path.abspath(__file__))
runs = [json.load(open(p)) for p in sorted(glob.glob(os.path.join(HERE, "results", "*.json")))
        if not os.path.basename(p).startswith(("smoke_", "dev_"))]
groups = collections.OrderedDict()
for r in runs:
    key = (r["model"].split("/")[-1], r["prompt"], r.get("tag", ""), r["n"])
    groups.setdefault(key, []).append(r)

def fmt(vals, pct=True):
    if len(vals) == 1:
        return f"{vals[0]:.1%}" if pct else f"{vals[0]:.2f}"
    m = sum(vals) / len(vals); rng = (max(vals) - min(vals)) / 2
    return (f"{m:.1%} ± {rng:.1%}" if pct else f"{m:.2f} ± {rng:.2f}")

print("| config | model | n | accuracy | macro-F1 | invalid | p50 s | p95 s | $/1k | seeds |")
print("|---|---|---|---|---|---|---|---|---|---|")
order = sorted(groups.items(), key=lambda kv: -sum(r["accuracy"] for r in kv[1]) / len(kv[1]))
for (model, prompt, tag, n), rs in order:
    cfg = prompt + (f" {tag}" if tag else "")
    if model.startswith("route("):
        cfg = f"routing {tag}"
    print(f"| {cfg} | {model} | {n} | {fmt([r['accuracy'] for r in rs])} | {fmt([r.get('macro_f1', 0) for r in rs])} | "
          f"{sum(r['invalid_outputs'] for r in rs) / len(rs):.0f} | {fmt([r['p50_latency_s'] for r in rs], False)} | "
          f"{fmt([r['p95_latency_s'] for r in rs], False)} | {sum(r['cost_per_1k_requests_usd'] for r in rs) / len(rs):.3f} | {len(rs)} |")

led = list(csv.DictReader(open(os.path.join(HERE, "ledger.csv"))))
inf = sum(float(r["cost"]) for r in led if "lora(sampling)" not in r["model"])
smp = sum(float(r["cost"]) for r in led if "lora(sampling)" in r["model"])
print(f"\nSpend: ${inf:.2f} inference, $0.00 training (free promotion), ${smp:.2f} tuned-model sampling (from ledger.csv, {len(led)} calls)")

best_name = os.environ.get("BEST", "glm-5p3-flash_v4_json_nothink_s7")
best = json.load(open(os.path.join(HERE, "results", best_name + ".json")))
print(f"\n## Misses of {best_name} ({sum(not r['correct'] for r in best['rows'])} of {best['n']})")
c = collections.Counter((r["label"], r["pred"]) for r in best["rows"] if not r["correct"])
for (g, p), k in c.most_common(12):
    ex = next(r for r in best["rows"] if r["label"] == g and r["pred"] == p)
    print(f"- {k}x gold **{g}** -> predicted **{p}**: \"{ex['text'][:110]}...\"")
