#!/usr/bin/env python3
"""frontier.png: x = $ per 1k requests (log), y = item F1, one point per configuration.
    python3 scripts/chart.py results/*.json
"""
import glob, json, os, sys
import matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
paths = sys.argv[1:] or [p for p in sorted(glob.glob(os.path.join(ROOT, "results", "*.json"))) if "smoke" not in p and "seed" not in p]
runs = [json.load(open(p)) for p in paths]
runs = [r for r in runs if "f1" in r]
fig, ax = plt.subplots(figsize=(9, 6), dpi=150)
colors = {"nemotron": "#6b8e23", "glm-5p3-flash": "#1f77b4", "gpt-oss": "#ff7f0e", "deepseek": "#9467bd", "glm-5p3": "#d62728", "kimi": "#8c564b", "route": "#17becf"}
def color(r):
    m = r["model"]
    for k, c in colors.items():
        if k in m and not (k == "glm-5p3" and "flash" in m):
            return c
    return "#333"
small_models = ("nemotron", "glm-5p3-flash")  # PROTOCOL.md roles: small = nemotron, glm-5p3-flash
runs = [r for r in runs if not (r["model"].startswith("filter(") and r["threshold"] > 0.9) and not (r["model"].startswith("route(") and r["threshold"] < 0.5)]
best_small = max([r for r in runs if any(r["model"].startswith("accounts/fireworks/models/" + s) for s in small_models)], key=lambda r: r["f1"], default=None)
for i, r in enumerate(sorted(runs, key=lambda r: r['cost_per_1k_requests_usd'])):
    x, y = max(r["cost_per_1k_requests_usd"], 1e-3), r["f1"]
    marker = "D" if r["model"].startswith("route") else ("*" if "kimi" in r["model"] else "o")
    ax.scatter(x, y, s=140 if r is best_small else 70, c=color(r), marker=marker, edgecolors="black" if r is best_small else "none", linewidths=1.5, zorder=3)
    short = {"v1_plain": "plain", "v2_rubric": "rubric", "v3_rubric_conf": "rubric+conf", "v2_rubric_json": "rubric+json", "v4_fewshot": "rubric+5-shot"}
    m = r["model"].split("/")[-1].replace("nemotron-lightning-3p5-30b-a3b", "nemotron-30b").replace("deepseek-v4p1-flash", "deepseek-flash")
    if m.startswith("route("): label = f"route flash->{m.split('->')[1][:-1]} thr{r['threshold']}"
    elif m.startswith("filter("): label = f"flash drop-items<{r['threshold']}"
    else: label = f"{m} {short.get(r['prompt'], r['prompt'])}" + (f" (n={r['n']})" if r["n"] < 140 else "")
    ax.annotate(label, (x, y), textcoords="offset points", xytext=(6, 4 if i % 2 == 0 else -10), fontsize=6.5)
if best_small:
    ax.annotate(f"best small: F1 {best_small['f1']:.3f} @ ${best_small['cost_per_1k_requests_usd']:.2f}/1k", (max(best_small["cost_per_1k_requests_usd"], 1e-3), best_small["f1"]),
                textcoords="offset points", xytext=(10, -34), fontsize=8, fontweight="bold", arrowprops=dict(arrowstyle="->"))
ax.set_xscale("log"); ax.set_xlabel("cost per 1k meetings, USD (log)"); ax.set_ylabel("item F1 on 150 locked test transcripts")
ax.set_title("Meeting transcript -> action items: quality vs. cost"); ax.grid(True, which="both", alpha=0.3)
fig.tight_layout(); out = os.path.join(ROOT, "frontier.png"); fig.savefig(out); print("saved", out, len(runs), "points")
