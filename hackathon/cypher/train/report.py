#!/usr/bin/env python3
"""Table + learning curve for train/TRAIN.md. Run: python3 train/report.py (from hackathon/cypher)."""
import csv, json, os
HERE = os.path.dirname(os.path.abspath(__file__))
CY = os.path.dirname(HERE)
STEPS = [("base", "train_base.json"), ("SFT", "train_sft.json"), ("SFT, pruned schema", "train_sft_pruned.json"),
         ("SFT seed 1", "train_sft_seed1.json"), ("SFT seed 2", "train_sft_seed2.json"),
         ("RFT r1 weighted", "train_rft_r1.json"), ("RFT r1 reject", "train_rft_r1_reject.json"), ("RFT r2", "train_rft_r2.json")]

spend = {}
if os.path.exists(os.path.join(HERE, "ledger.csv")):
    for r in csv.DictReader(open(os.path.join(HERE, "ledger.csv"))):
        spend[r["note"]] = spend.get(r["note"], 0) + float(r["cost"])

rows = []
print("| config | accuracy | lenient | error | empty | easy | medium | hard | in tok/call | out tok/call | eval spend |")
print("|---|---|---|---|---|---|---|---|---|---|---|")
for name, f in STEPS:
    p = os.path.join(CY, "results", f)
    if not os.path.exists(p):
        continue
    d = json.load(open(p))
    t = d["by_tier"]
    sp = spend.get(f"eval {os.path.splitext(f)[0]}", d["cost_total_usd"])
    rows.append((name, d))
    print(f"| {name} | {d['accuracy']:.1%} | {d['accuracy_lenient']:.1%} | {d['error_rate']:.1%} | {d['empty_rate']:.1%} | "
          f"{t.get('easy', {}).get('accuracy', 0):.1%} | {t.get('medium', {}).get('accuracy', 0):.1%} | {t.get('hard', {}).get('accuracy', 0):.1%} | "
          f"{d['in_tokens_per_call']:.0f} | {d['out_tokens_per_call']:.1f} | ${sp:.3f} |")
print("\nledger by note:")
for k, v in spend.items():
    print(f"  {k}: ${v:.4f}")
print(f"  TOTAL: ${sum(spend.values()):.4f}")

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
curve = [(n, d) for n, d in rows if "pruned" not in n and "seed" not in n]
fig, ax = plt.subplots(figsize=(7, 4.2))
xs = range(len(curve))
ax.plot(xs, [d["accuracy"] * 100 for _, d in curve], "o-", color="#2a6fdb", lw=2, label="accuracy (exact rows)")
ax.plot(xs, [d["error_rate"] * 100 for _, d in curve], "s--", color="#d9534f", lw=1.5, label="execution error rate")
ax.plot(xs, [d["empty_rate"] * 100 for _, d in curve], "^--", color="#999999", lw=1.5, label="empty result rate")
for x, (_, d) in zip(xs, curve):
    ax.annotate(f"{d['accuracy']:.1%}", (x, d["accuracy"] * 100), textcoords="offset points", xytext=(0, 8), ha="center", fontsize=9)
ax.set_xticks(list(xs)); ax.set_xticklabels([n.replace("RFT r1 ", "RFT r1\n") for n, _ in curve])
ax.set_ylabel("% of 200 locked test rows"); ax.set_ylim(0, 100); ax.grid(alpha=0.3)
ax.set_title("Muse Glimmer 30B LoRA, text-to-Cypher (locked 200-row set)")
ax.legend(loc="upper left", fontsize=8)
fig.tight_layout()
fig.savefig(os.path.join(HERE, "curve.png"), dpi=150)
print("saved train/curve.png")
