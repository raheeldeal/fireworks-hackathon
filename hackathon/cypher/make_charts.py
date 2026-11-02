#!/usr/bin/env python3
"""Two charts for the submission: the cost/accuracy frontier and the coverage curve."""
import glob, json, os, matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

def pick(pat):
    ps = sorted(glob.glob(f"results/{pat}"))
    return json.load(open(ps[0])) if ps else None

pts = []
def add(label, path, ours=False):
    if not os.path.exists(f"results/{path}"): return
    d = json.load(open(f"results/{path}"))
    c = d.get("cost_per_1k_requests_usd") or 0
    if not c: return
    pts.append((label, c, d["accuracy"]*100, ours, d.get("n")))

add("kimi-k3 (frontier open)", "kimi-k3_v1_plain_n100.json")
add("glm-5p3 (large)", "glm-5p3_v1_plain_n100.json")
add("deepseek-v4.1-flash", "deepseek-v4p1-flash_v1_plain_n200.json")
add("glm-5p3-flash (small)", "glm-5p3-flash_v1_plain_n200.json")
add("Muse Glimmer 30B base", "train_base.json")
add("+ harness (repair)", "harness_repair1_rdefault.json", True)
add("+ harness (vote3)", "harness_vote3.json", True)
add("+ harness (route)", "harness_route_big.json", True)
add("FINE-TUNED (SFT)", "train_sft.json", True)
add("FINE-TUNED + pruned schema", "train_sft_pruned.json", True)

fig, ax = plt.subplots(figsize=(9,5.5), dpi=150)
for label, c, a, ours, n in pts:
    ax.scatter(c, a, s=190 if ours else 90, color="#d9480f" if ours else "#495057",
               marker="*" if "FINE-TUNED" in label else "o", zorder=3)
    ax.annotate(f"{label}\n{a:.1f}%  ${c:.3f}/1k", (c, a), textcoords="offset points",
                xytext=(9, 5), fontsize=8, color="#d9480f" if ours else "#212529")
ax.set_xscale("log"); ax.set_xlabel("Cost per 1,000 questions (USD, log scale)")
ax.set_ylabel("Execution accuracy on locked 200-question set (%)")
ax.set_title("Text-to-Cypher: quality vs. cost\nneo4j/text2cypher-2025v1, scored by executing on live graphs")
ax.grid(alpha=0.3)
best_closed = max((a for l,c,a,o,n in pts if not o), default=0)
ax.axhline(best_closed, ls="--", lw=1, color="#adb5bd")
ax.text(ax.get_xlim()[0]*1.1, best_closed+0.4, "best off-the-shelf model", fontsize=8, color="#868e96")
plt.tight_layout(); plt.savefig("frontier.png"); print("frontier.png")

cov = json.load(open("results/coverage_curve.json"))
fig, ax = plt.subplots(figsize=(7,4.5), dpi=150)
xs = [c["coverage"]*100 for c in cov][::-1]; ys = [c["precision"]*100 for c in cov][::-1]
ax.plot(xs, ys, "-o", color="#d9480f", lw=2)
for c in cov:
    ax.annotate(c["policy"], (c["coverage"]*100, c["precision"]*100), textcoords="offset points", xytext=(6,6), fontsize=8)
ax.set_xlabel("Coverage: share of questions answered (%)")
ax.set_ylabel("Precision: accuracy among answered (%)")
ax.set_title("Answer only when the system is confident\n(agreement of three executed attempts)")
ax.grid(alpha=0.3)
plt.tight_layout(); plt.savefig("coverage.png"); print("coverage.png")
