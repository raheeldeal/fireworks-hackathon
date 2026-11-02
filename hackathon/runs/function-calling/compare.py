#!/usr/bin/env python3
"""Side-by-side table of every results/*.json (adapted from hackathon/eval/compare.py; adds partial score and seeds).
Prints the markdown table used in RESULTS.md."""
import glob, json, os, re, sys, statistics
HERE = os.path.dirname(os.path.abspath(__file__))
paths = [a for a in sys.argv[1:] if not a.startswith("--")] or sorted(glob.glob(os.path.join(HERE, "results", "*.json")))
runs = {}
for p in paths:
    d = json.load(open(p))
    stem = os.path.basename(p)[:-5]
    if isinstance(d, list):   # route sweep: keep the best-accuracy and the cheapest threshold (all thresholds: --all-routes)
        keep = d if "--all-routes" in sys.argv else {id(max(d, key=lambda r: (r["accuracy"], -r["cost_per_1k_requests_usd"]))),
                                                     id(min(d, key=lambda r: r["cost_per_1k_requests_usd"]))}
        for r in d:
            if keep is d or id(r) in keep:
                runs[f"{stem}:{r['threshold']}"] = dict(r, seeds=1, stem=stem)
        continue
    if "accuracy" not in d or stem.startswith("smoke"):
        continue
    base = re.sub(r"_seed\d+$", "", stem)
    g = runs.setdefault(base, {"accs": [], "partials": [], "lat50": [], "lat95": [], "costs": [], "inv": [], "model": d["model"], "n": d["n"], "stem": base})
    for k, v in (("accs", d["accuracy"]), ("partials", d["accuracy_partial"]), ("lat50", d["p50_latency_s"]), ("lat95", d["p95_latency_s"]),
                 ("costs", d["cost_per_1k_requests_usd"]), ("inv", d["invalid_outputs"])):
        g[k].append(v)
print("| config | model | n | strict acc | partial | invalid | p50 s | p95 s | $/1k | seeds |")
print("|---|---|---|---|---|---|---|---|---|---|")
for stem, g in sorted(runs.items(), key=lambda kv: -(kv[1].get("accuracy") if "accuracy" in kv[1] else statistics.mean(kv[1]["accs"]))):
    if "accs" in g:
        k = len(g["accs"]); acc = statistics.mean(g["accs"]); rng = (max(g["accs"]) - min(g["accs"])) if k > 1 else 0
        acc_s = f"{acc:.1%}" + (f" ± {rng/2:.1%}" if k > 1 else "")
        print(f"| {stem} | {g['model'].split('/')[-1]} | {g['n']} | {acc_s} | {statistics.mean(g['partials']):.1%} | {statistics.mean(g['inv']):.0f} | "
              f"{statistics.mean(g['lat50']):.2f} | {statistics.mean(g['lat95']):.2f} | {statistics.mean(g['costs']):.3f} | {k} |")
    else:
        print(f"| {stem} (esc {g['escalated_frac']:.0%}) | {g['model']} | {g['n']} | {g['accuracy']:.1%} | {g['accuracy_partial']:.1%} | 0 | "
              f"{g['p50_latency_s']:.2f} | {g['p95_latency_s']:.2f} | {g['cost_per_1k_requests_usd']:.3f} | 1 |")
