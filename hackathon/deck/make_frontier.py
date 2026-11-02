"""Cost vs accuracy frontier on the same 100 exam questions (the ones Claude Opus 5 answered).
Numbers recomputed from hackathon/cypher/results/*.json, scored on live Neo4j."""
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

# (label, cost per 1k questions in $, correct out of 100, kind)
pts = [
    ("Claude Opus 5", 9.00, 47, "closed"),
    ("Kimi K3", 6.36, 49, "open"),
    ("GLM 5.3", 3.13, 48, "open"),
    ("DeepSeek V4.1 Flash", 0.82, 47, "open"),
    ("GLM 5.3 Flash", 0.24, 58, "small"),
    ("GLM Flash + harness", 0.77, 56, "small"),
    ("Muse 30B", 1.89, 51, "small"),
    ("Muse 30B + SFT + RFT", 1.86, 58, "small"),
]
col = {"closed": "#000000", "open": "#9a9a9a", "small": "#000000"}

fig, ax = plt.subplots(figsize=(19.2, 10.8), dpi=100)
for name, c, a, k in pts:
    ax.scatter(c, a, s=900 if k == "closed" else 500, color="white" if k == "closed" else col[k],
               edgecolor="black", linewidth=4 if k == "closed" else 1, zorder=3)
    dy = -2.2 if name in ("Muse 30B + SFT + RFT", "GLM Flash + harness") else 1.4
    ax.annotate(name, (c, a), xytext=(0, 26 if dy > 0 else -40), textcoords="offset points",
                ha="center", fontsize=20, weight="bold" if k != "open" else "normal")

ax.set_xscale("log")
ax.set_xlim(0.15, 16)
ax.set_ylim(40, 65)
ax.set_xticks([0.25, 0.5, 1, 2, 4, 8])
ax.set_xticklabels(["$0.25", "$0.50", "$1", "$2", "$4", "$8"], fontsize=20)
ax.tick_params(axis="y", labelsize=20)
ax.set_xlabel("Cost per 1,000 questions (log scale)", fontsize=22)
ax.set_ylabel("Correct out of 100", fontsize=22)
for s in ("top", "right"):
    ax.spines[s].set_visible(False)
ax.annotate("Better", xy=(0.2, 63.5), xytext=(0.55, 60.5), fontsize=22, weight="bold",
            arrowprops=dict(arrowstyle="->", lw=3))
fig.suptitle("Cheaper and more accurate than the frontier", fontsize=40, weight="bold", x=0.06, ha="left")
fig.text(0.06, 0.015, "Same 100 held-out questions, every query run on live Neo4j. Fine-tuned cost measured through the training sampler.",
         fontsize=15, color="#555555")
fig.subplots_adjust(left=0.08, right=0.97, top=0.88, bottom=0.12)
fig.savefig("/Users/raheelahmed/fireworks-hackathon/hackathon/deck/frontier.png")
print("ok")
