#!/usr/bin/env python3
"""frontier.png: x = $ per 1k requests (log), y = accuracy, one point per configuration; best small point labelled."""
import glob, json, os, sys
import matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt

HERE = os.path.dirname(os.path.abspath(__file__))
paths = sys.argv[1:] or sorted(glob.glob(os.path.join(HERE, "results", "*.json")))
paths = [p for p in paths if "/probe/" not in p]
# prefer the _retry version of a file when it exists; drop single-seed files when a 3-seed aggregate exists
pset = set(paths)
def keep(p):
    if "_seed" in p: return False
    if not p.endswith("_retry.json") and p.replace(".json", "_retry.json") in pset: return False
    if "_3seeds" not in p and p.replace(".json", "_3seeds.json") in pset: return False
    return True
runs = [json.load(open(p)) for p in paths if keep(p)]
runs = [r for r in runs if not r.get("truncated_by_cap") and r["n"] >= 100]
SMALL = ("nemotron", "glm-5p3-flash", "gpt-oss", "deepseek")
fig, ax = plt.subplots(figsize=(9, 6))
best = None
for r in runs:
    name = r["model"].split("/")[-1]
    routed = "->" in r["model"]
    small = name.startswith(SMALL) and not routed
    frontier = "kimi" in name
    color = "#2a9d8f" if small else ("#e76f51" if frontier else ("#8338ec" if routed else "#457b9d"))
    marker = "o" if small else ("*" if frontier else ("D" if routed else "s"))
    ax.scatter(r["cost_per_1k_requests_usd"], r["accuracy"], c=color, marker=marker, s=110 if frontier else 70, edgecolor="black", linewidth=0.5, zorder=3)
    label = (("route " if routed else name + " ") + r["prompt"].replace("_retry", "").replace("v1_plain_", "").replace("v1_plain", "plain").replace("_3seeds", " (3 seeds)").replace("conf_route_self", "self-conf").replace("route_", ""))
    if len(label) > 44: label = label[:42] + "…"
    ax.annotate(label, (r["cost_per_1k_requests_usd"], r["accuracy"]), fontsize=6.5, xytext=(4, 3 + 9 * (hash(label) % 3 - 1)), textcoords="offset points")
    if small and (best is None or r["accuracy"] > best["accuracy"]):
        best = r
if best:
    ax.annotate(f"best small: {best['accuracy']:.1%} @ ${best['cost_per_1k_requests_usd']:.2f}/1k", (best["cost_per_1k_requests_usd"], best["accuracy"]),
                xytext=(-10, -40), textcoords="offset points", fontsize=9, fontweight="bold", ha="right",
                arrowprops=dict(arrowstyle="->", lw=1))
ax.set_xscale("log"); ax.set_xlabel("cost per 1k requests (USD, log scale)"); ax.set_ylabel("accuracy (hidden tests pass)")
ax.set_title("Code fix (HumanEvalFix, 164 problems): accuracy vs. cost per configuration")
ax.grid(True, which="both", alpha=0.3); ax.set_ylim(0.7, 1.01)
from matplotlib.lines import Line2D
ax.legend(handles=[Line2D([], [], marker="o", color="#2a9d8f", ls="", label="small model"), Line2D([], [], marker="s", color="#457b9d", ls="", label="large model"),
                   Line2D([], [], marker="D", color="#8338ec", ls="", label="routed small→large"), Line2D([], [], marker="*", color="#e76f51", ls="", label="frontier open (kimi-k3)")], loc="lower right", fontsize=8)
out = os.path.join(HERE, "frontier.png"); fig.tight_layout(); fig.savefig(out, dpi=150); print("saved", out, f"({len(runs)} points)")
