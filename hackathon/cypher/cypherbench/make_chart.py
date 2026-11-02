"""CypherBench held-out exam chart: accuracy (95% CI) next to the main-test score, and $/question. Reads results/cb_*.json."""
import json, os
import matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt
CY = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ROWS = [  # label, CypherBench result tag, main-test accuracy (this repo, n=200)
    ("deepseek-v4p1-flash, plain", "cb_deepseek-v4p1-flash", None),
    ("Muse Glimmer 30B base, plain", "cb_r1_base", 0.505),
    ("glm-5p3-flash, plain", "cb_glm-5p3-flash", 0.61),
    ("kimi-k3, plain", "cb_kimi-k3", 0.63),
    ("Muse base + harness (r5_full)", "cb_r5_full", 0.56),
    ("SFT ft1 + harness (r6_ft1)", "cb_r6_ft1", 0.66),
    ("SFT ftbx +9 graphs + harness (r6bx_ftbx)", "cb_r6bx_ftbx", 0.685),
]
INK, MUTED, GRID, BLUE = "#1f2328", "#6e7781", "#d8dee4", "#2f6fd6"
data = []
for label, tag, main in ROWS:
    p = os.path.join(CY, "results", tag + ".json")
    s = json.load(open(p))["summary"] if os.path.exists(p) else None
    data.append((label, s, main))
fig, (ax, ax2) = plt.subplots(1, 2, figsize=(13, 5.2), gridspec_kw={"width_ratios": [3, 1.2]}, sharey=True)
for i, (label, s, main) in enumerate(data):
    if s:
        a, (lo, hi) = s["accuracy"] * 100, (c * 100 for c in s["ci95"])
        ax.plot([lo, hi], [i, i], color=BLUE, lw=2, solid_capstyle="round", zorder=2)
        ax.scatter(a, i, s=70, color=BLUE, edgecolor="white", linewidth=2, zorder=3)
        ax.text(hi + 1.2, i, f"{a:.0f}%", va="center", color=INK, fontsize=10, fontweight="bold")
        ax2.barh(i, s["cost_per_question"] * 1000, height=0.55, color=BLUE)
        ax2.text(s["cost_per_question"] * 1000 * 1.15, i, f"${s['cost_per_question']*1000:.2f}", va="center", color=INK, fontsize=9)
    else:
        ax.text(41, i, "pending: needs the adapter owner's key", va="center", color=MUTED, fontsize=9, style="italic")
    if main is not None:
        ax.scatter(main * 100, i, s=60, facecolor="white", edgecolor=MUTED, linewidth=2, zorder=3)
ax.set_yticks(range(len(data)), [d[0] for d in data], color=INK)
ax.set_xlim(40, 90); ax.set_xlabel("execution accuracy (%)", color=MUTED)
ax.scatter([], [], s=70, color=BLUE, label="CypherBench held-out, n=100 (line = 95% CI)")
ax.scatter([], [], s=60, facecolor="white", edgecolor=MUTED, linewidth=2, label="main test, n=200 (seen graphs)")
ax.legend(loc="lower left", bbox_to_anchor=(0, 1.0), ncol=2, frameon=False, fontsize=9)
ax2.set_xscale("log"); ax2.set_xticks([0.1, 1, 10], ["$0.1", "$1", "$10"]); ax2.set_xlabel("$ per 1k questions (log)", color=MUTED); ax2.set_xlim(0.1, 30)
for a_ in (ax, ax2):
    a_.grid(axis="x", color=GRID, lw=0.8); a_.set_axisbelow(True)
    for sp in ("top", "right", "left"): a_.spines[sp].set_visible(False)
    a_.spines["bottom"].set_color(GRID); a_.tick_params(colors=MUTED, length=0)
fig.suptitle("Final exam on unseen graphs (CypherBench flight_accident + nba): nothing collapses, harness adds +9 pp on Muse base",
             x=0.01, ha="left", color=INK, fontsize=12, fontweight="bold")
fig.text(0.01, 0.905, "Same harness and scorer as the main test. Retrieval finds no same-graph examples on these graphs. Single run per config.",
         color=MUTED, fontsize=9)
fig.tight_layout(rect=(0, 0, 1, 0.86))
out = os.path.join(CY, "cypherbench", "cypherbench_results.png"); fig.savefig(out, dpi=160); print(out)
