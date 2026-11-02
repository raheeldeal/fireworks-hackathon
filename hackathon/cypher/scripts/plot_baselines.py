"""baselines.png: execution accuracy (strict) per model, sorted ascending, $/1k under each bar."""
import json, glob, os
import matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt
HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FRONTIER = {"kimi-k3"}
NAMES = {"nemotron-lightning-3p5-30b-a3b": "nemotron-lightning\n30B-A3B (reasoning off)", "glm-5p3-flash": "glm-5p3-flash",
         "deepseek-v4p1-flash": "deepseek-v4p1-flash", "glm-5p3": "glm-5p3", "kimi-k3": "kimi-k3"}
res = [json.load(open(f)) for f in glob.glob(os.path.join(HERE, "results", "*.json"))]
res = sorted([r for r in res if r["model"] != "gold"], key=lambda r: r["accuracy"])
fig, ax = plt.subplots(figsize=(9, 5.2))
xs = range(len(res))
for i, r in enumerate(res):
    m = r["model"].split("/")[-1]
    fr = m in FRONTIER
    ax.bar(i, r["accuracy"] * 100, color="#c2553a" if fr else "#3a6ea5", width=0.62)
    ax.bar(i, r["accuracy_lenient"] * 100, color="none", edgecolor="#888", linestyle="--", width=0.62)
    ax.text(i, r["accuracy"] * 100 + 1, f"{r['accuracy']:.0%}", ha="center", fontsize=11, fontweight="bold")
    ax.text(i, -9, f"${r['cost_per_1k_requests_usd']:.2f} / 1k\nn={r['n']}", ha="center", va="top", fontsize=9, color="#333")
ax.set_xticks(list(xs))
ax.set_xticklabels([NAMES.get(r["model"].split("/")[-1], r["model"].split("/")[-1]) + ("\n[frontier]" if r["model"].split("/")[-1] in FRONTIER else "\n[open model]") for r in res], fontsize=9)
ax.tick_params(axis="x", pad=34)
ax.set_ylim(0, 100); ax.set_ylabel("execution accuracy, strict (%)")
ax.set_title("Text-to-Cypher baselines: 200-row locked test (neo4j/text2cypher-2025v1, 5 live graphs)", fontsize=11)
from matplotlib.patches import Patch
ax.legend(handles=[Patch(color="#3a6ea5", label="open model"), Patch(color="#c2553a", label="frontier open model"),
                   Patch(facecolor="none", edgecolor="#888", linestyle="--", label="lenient accuracy")], loc="upper left", fontsize=9)
for s in ("top", "right"): ax.spines[s].set_visible(False)
fig.tight_layout(); fig.savefig(os.path.join(HERE, "baselines.png"), dpi=150)
print("saved baselines.png")
