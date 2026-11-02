#!/usr/bin/env python3
"""frontier.png: x = cost per 1k requests (log), y = accuracy; one point per configuration (seed 7 or mean over seeds)."""
import glob, json, os, collections
import matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt
HERE = os.path.dirname(os.path.abspath(__file__))
runs = [json.load(open(p)) for p in sorted(glob.glob(os.path.join(HERE, "results", "*.json"))) if "smoke_" not in p and "dev_" not in p]
groups = collections.defaultdict(list)
for r in runs:
    groups[(r["model"].split("/")[-1], r["prompt"], r.get("tag", ""))].append(r)
pts = []
KEEP_ROUTES = {"route(nemotron-lightning-3p5-30b-a3b->deepseek-v4p1-flash)": "t0.95", "route(glm-5p3-flash->deepseek-v4p1-flash)": "t0.7"}
for (model, prompt, tag), rs in groups.items():
    if model.startswith("route(") and KEEP_ROUTES.get(model) != tag:
        continue  # one representative routing point per pair keeps the chart readable
    acc = sum(r["accuracy"] for r in rs) / len(rs); cost = sum(r["cost_per_1k_requests_usd"] for r in rs) / len(rs)
    pts.append((model, prompt, tag, acc, max(cost, 1e-4), len(rs)))
SMALL = ("nemotron-lightning-3p5-30b-a3b", "glm-5p3-flash", "muse")
fig, ax = plt.subplots(figsize=(11, 7))
for model, prompt, tag, acc, cost, n in pts:
    small = any(model.startswith(s) for s in SMALL) or model.startswith("route(")
    color = "#1f77b4" if small else ("#d62728" if "kimi" in model else "#7f7f7f")
    marker = "*" if "lora" in model else "o"
    ax.scatter(cost, acc, s=220 if marker == "*" else 70, color=color, marker=marker, zorder=3)
    short = model.replace("nemotron-lightning-3p5-30b-a3b", "nemotron-3.5-30b").replace("route(", "route(").replace("accounts/fireworks/models/", "")
    label = f"{short}\n{prompt}{(' ' + tag) if tag else ''}" + (f" ({n} seeds)" if n > 1 else "")
    offs = [(6, 6), (6, -14), (-6, 8), (-6, -16), (8, -4), (-8, 2)]
    i = len(ax.texts) % len(offs)
    ax.annotate(label, (cost, acc), fontsize=6.5, xytext=offs[i], textcoords="offset points", ha="left" if offs[i][0] > 0 else "right")
if pts:
    best = max((p for p in pts if any(p[0].startswith(s) for s in SMALL)), key=lambda p: p[3], default=None)
    if best:
        ax.annotate("best small model", (best[4], best[3]), fontsize=9, fontweight="bold", color="#1f77b4", xytext=(-60, -40), textcoords="offset points", arrowprops=dict(arrowstyle="->", color="#1f77b4"))
ax.set_xscale("log"); ax.set_xlabel("cost per 1k requests (USD, log)"); ax.set_ylabel("accuracy (199-row LEDGAR test set)")
ax.set_title("Legal clause classification: accuracy vs cost"); ax.grid(True, which="both", alpha=0.3)
fig.tight_layout(); fig.savefig(os.path.join(HERE, "frontier.png"), dpi=150)
print("wrote frontier.png with", len(pts), "points")
