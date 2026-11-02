#!/usr/bin/env python3
"""Print everything RESULTS.md needs from results/*.json: results table (markdown), same-100-row frontier comparison,
seed variance, confidence calibration, routing sweep table, misses for the best small config, spend from ledger."""
import csv, glob, json, os, statistics, collections
HERE = os.path.dirname(os.path.abspath(__file__))
R = {}
for p in sorted(glob.glob(os.path.join(HERE, "results", "*.json"))):
    d = json.load(open(p))
    if "rows" in d:
        R[os.path.basename(p)[:-5]] = d
kimi = R.get("kimi-k3_v1_plain_n100")
kimi_ids = {r["id"] for r in kimi["rows"]} if kimi else set()

def short(m): return m.split("/")[-1]
def acc_on(d, ids):
    rows = [r for r in d["rows"] if r["id"] in ids]
    return sum(r["correct"] for r in rows) / len(rows) if rows else float("nan")

# group seeds
groups = collections.defaultdict(list)
for k, d in R.items():
    base = k.rsplit("_s", 1)[0] if d.get("seed") else k
    groups[base].append(d)

print("## Results table")
print("| config | model | accuracy | acc on kimi's 100 rows | invalid | p50 s | p95 s | $/1k | seeds |")
print("|---|---|---|---|---|---|---|---|---|")
rows_out = []
for base, ds in sorted(groups.items(), key=lambda kv: -statistics.mean(x["accuracy"] for x in kv[1])):
    d0 = [x for x in ds if not x.get("seed")] or ds
    d0 = d0[0]
    accs = [x["accuracy"] for x in ds]
    acc_s = f"{statistics.mean(accs):.1%}" + (f" ± {max(accs)-min(accs):.1%} (n={len(accs)}: {', '.join(f'{a:.1%}' for a in accs)})" if len(accs) > 1 else "")
    a100 = acc_on(d0, kimi_ids) if kimi_ids else float("nan")
    print(f"| {d0['prompt']} | {short(d0['model'])} | {acc_s} | {a100:.1%} | {d0['invalid_outputs']} | {d0['p50_latency_s']:.2f} | {d0['p95_latency_s']:.2f} | {d0['cost_per_1k_requests_usd']:.3f} | {len(accs)} |")

print("\n## Routing sweeps (small model answers; escalate when invalid or confidence < threshold)")
for p in sorted(glob.glob(os.path.join(HERE, "results", "routing_*.json"))):
    d = json.load(open(p))
    S, B = json.load(open(d["small"])), json.load(open(d["big"]))
    print(f"\n**{short(S['model'])} + {S['prompt']} → {short(B['model'])} + {B['prompt']}** (n={d['n']})")
    print("| threshold | escalated | accuracy | $/1k | p50 s | p95 s |\n|---|---|---|---|---|---|")
    for r in d["sweep"]:
        print(f"| {r['threshold']:.2f} | {r['escalated_frac']:.1%} | {r['accuracy']:.1%} | {r['cost_per_1k_requests_usd']:.3f} | {r['p50_latency_s']:.2f} | {r['p95_latency_s']:.2f} |")

print("\n## Confidence calibration (self-reported confidence vs. actual accuracy)")
for k, d in sorted(R.items()):
    confs = [r for r in d["rows"] if r.get("confidence") is not None]
    if len(confs) < 100 or d.get("seed"):
        continue
    bins = collections.defaultdict(list)
    for r in confs:
        bins[min(0.95, round(r["confidence"] * 20) / 20)].append(r["correct"])
    s = ", ".join(f"≥{b:.2f}: {statistics.mean(v):.0%} (n={len(v)})" for b, v in sorted(bins.items()) if len(v) >= 5)
    print(f"- {k}: {s}")

print("\n## Spend")
tot = collections.defaultdict(float); n = 0
for r in csv.DictReader(open(os.path.join(HERE, "ledger.csv"))):
    tot[short(r["model"])] += float(r["cost"]); n += 1
print(f"ledger rows {n}, total ${sum(tot.values()):.4f}; by model: " + ", ".join(f"{m} ${c:.3f}" for m, c in sorted(tot.items(), key=lambda kv: -kv[1])))

import sys
best = sys.argv[1] if len(sys.argv) > 1 else None
if best and best in R:
    d = R[best]
    print(f"\n## Misses for {best} ({d['accuracy']:.1%})")
    conf = collections.Counter((r["label"], r["pred"]) for r in d["rows"] if not r["correct"])
    for (g, p), c in conf.most_common(40):
        ex = next(r["text"] for r in d["rows"] if r["label"] == g and r["pred"] == p)
        print(f"- gold **{g}** → pred **{p}** ×{c}: \"{ex[:90]}\"")
