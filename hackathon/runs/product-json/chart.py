#!/usr/bin/env python3
"""frontier.png: x = $ per 1k requests (log), y = all-fields accuracy, one point per config; best small-model point labelled."""
import glob, json, os, sys
import matplotlib; matplotlib.use("Agg"); import matplotlib.pyplot as plt
HERE = os.path.dirname(os.path.abspath(__file__))
paths = sys.argv[1:] or sorted(glob.glob(os.path.join(HERE, "results", "*.json")))
runs = [json.load(open(p)) for p in paths if ("_s7" in p or "route" in p) and "_t1.json" not in p and "_t2.json" not in p]
SMALL = ("nemotron", "glm-5p3-flash", "gpt-oss", "deepseek")
fig, ax = plt.subplots(figsize=(9, 6), dpi=150)
colors = {"nemotron-lightning-3p5-30b-a3b": "#1b9e77", "glm-5p3-flash": "#d95f02", "gpt-oss-120b": "#7570b3", "deepseek-v4p1-flash": "#e7298a", "glm-5p3": "#66a61e", "kimi-k3": "#e6ab02"}
best = None
for i, r in enumerate(sorted(runs, key=lambda r: r["cost_per_1k_requests_usd"])):
    m = r["model"].split("/")[-1]; base = m.split("->")[0]
    c = colors.get(base, "#666"); marker = "D" if "->" in m else ("s" if r.get("json_mode") else "o")
    ax.scatter(r["cost_per_1k_requests_usd"], r["accuracy"], s=70, color=c, marker=marker, edgecolor="black", linewidth=0.5, zorder=3)
    lab = f"{m.replace('-lightning-3p5-30b-a3b','').replace('glm-5p3-flash->','→')} {r['prompt'].replace('v1_plain','plain').replace('v2_rubric','rubric').replace('v3_fewshot','few-shot').replace('_jsonmode',' +json').replace('route_','route ')}"
    ax.annotate(lab, (r["cost_per_1k_requests_usd"], r["accuracy"]), fontsize=6.5, xytext=(4, 3 if i % 2 == 0 else -9), textcoords="offset points")
    if base.startswith(SMALL) and (best is None or r["accuracy"] > best["accuracy"]): best = r
if best:
    ax.scatter(best["cost_per_1k_requests_usd"], best["accuracy"], s=260, facecolor="none", edgecolor="red", linewidth=2, zorder=4)
    ax.annotate(f"best small: {best['accuracy']:.1%} @ ${best['cost_per_1k_requests_usd']:.2f}/1k", (best["cost_per_1k_requests_usd"], best["accuracy"]), xytext=(0, -18), textcoords="offset points", color="red", fontsize=8, ha="center")
ax.set_xscale("log"); ax.set_xlabel("cost per 1,000 requests (USD, log)"); ax.set_ylabel("all-fields-correct accuracy"); ax.set_title("Product listing → strict JSON: accuracy vs. cost (Fireworks serverless, temp 0)")
ax.grid(True, which="both", alpha=0.3); ax.set_ylim(0.6, 1.0)
from matplotlib.lines import Line2D
ax.legend(handles=[Line2D([], [], marker="o", color="gray", linestyle="", label="plain/rubric/few-shot"), Line2D([], [], marker="s", color="gray", linestyle="", label="JSON schema mode"), Line2D([], [], marker="D", color="gray", linestyle="", label="routing small→large")], loc="lower right", fontsize=8)
fig.tight_layout(); out = os.path.join(HERE, "frontier.png"); fig.savefig(out); print("saved", out, "from", len(runs), "runs")
