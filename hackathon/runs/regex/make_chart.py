#!/usr/bin/env python3
"""frontier.png: x = $ per 1k requests (log), y = accuracy, one point per configuration.
    venv/bin/python make_chart.py [--best <results file basename>]
"""
import glob
import json
import os
import sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
best_name = None
if "--best" in sys.argv:
    best_name = sys.argv[sys.argv.index("--best") + 1]

pts = []
for p in sorted(glob.glob(os.path.join(HERE, "results", "*.json"))):
    try:
        r = json.load(open(p))
    except Exception:
        continue
    b = os.path.basename(p)
    if "accuracy" not in r or "_seed" in b or b.startswith("heldout_") or b.endswith("_conf.json"):
        continue  # seed re-runs, held-out checks and the logprobs duplicate of the rubric run are not separate configurations
    name = os.path.basename(p)[:-5]
    label = f"{r['model'].split('/')[-1]} · {r['prompt']}"
    pts.append((max(r["cost_per_1k_requests_usd"], 1e-4), r["accuracy"], label, name, r["model"]))
if not pts:
    sys.exit("no results")

fig, ax = plt.subplots(figsize=(10, 6.5), dpi=130)
families = {}
for x, y, label, name, model in pts:
    fam = "routing" if model.startswith("route[") else ("fine-tuned" if "sft" in name or "raheeldeal" in model else model.split("/")[-1])
    families.setdefault(fam, []).append((x, y, label, name))
colors = plt.cm.tab10.colors
for i, (fam, items) in enumerate(sorted(families.items())):
    xs, ys = [it[0] for it in items], [it[1] for it in items]
    ax.scatter(xs, ys, s=60, color=colors[i % 10], label=fam, zorder=3, edgecolor="white", linewidth=0.8)
    for x, y, label, name in items:
        is_best = name == best_name
        short = label.split(" · ")[1]
        if fam == "fine-tuned":
            short = "base, plain prompt" if "_base_" in name else "LoRA, plain prompt"
        if short.startswith("v2_rubric_conf_thr"):
            short = "t" + short.split("thr")[1]  # routing threshold
        ax.annotate(short if len(items) > 1 else "", (x, y), textcoords="offset points", xytext=(4, -9 if fam == "routing" else 4), fontsize=7, color="#444")
        if is_best:
            ax.annotate(f"best small config\n{label}\n{y:.1%} @ ${x:.3f}/1k", (x, y), textcoords="offset points", xytext=(-150, -80),
                        fontsize=8, fontweight="bold", arrowprops=dict(arrowstyle="->", color="black"),
                        bbox=dict(boxstyle="round", fc="#fff8dc", ec="#333"))
ax.set_xscale("log")
ax.set_xlabel("cost per 1,000 requests (USD, log scale)")
ax.set_ylabel("accuracy (regex matches all 10 positives and rejects all 10 negatives)")
ax.set_title("Natural language → regex: accuracy vs. cost, 200-row KB13 test set")
ax.grid(True, which="both", alpha=0.25)
ax.set_ylim(0, 1.04)
ax.yaxis.set_major_formatter(matplotlib.ticker.PercentFormatter(1.0))
ax.legend(loc="lower right", fontsize=8, title="model / family")
fig.tight_layout()
out = os.path.join(HERE, "frontier.png")
fig.savefig(out)
print("saved", out, "with", len(pts), "points")
