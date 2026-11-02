#!/usr/bin/env python3
"""frontier.png: x = cost per 1k requests (log), y = set-F1; one point per configuration."""
import glob, json, os
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
HERE = os.path.dirname(os.path.abspath(__file__))
runs = []
for p in sorted(glob.glob(os.path.join(HERE, "results", "*.json"))):
    r = json.load(open(p))
    if "accuracy" not in r or r.get("seed") not in (7, None):
        continue
    runs.append(r)
fig, ax = plt.subplots(figsize=(9, 6))
best_small = None
for r in runs:
    name = f"{r['model'].split('/')[-1]}\n{r['prompt']}"
    x, y = max(r["cost_per_1k_requests_usd"], 1e-4), r["accuracy"]
    is_route = r["model"].startswith("route")
    small = any(k in r["model"] for k in ("nemotron", "flash", "route"))
    c = "#1f77b4" if small else ("#d62728" if "kimi" in r["model"] else "#7f7f7f")
    ax.scatter(x, y, s=60, c=c, marker="^" if is_route else "o", zorder=3)
    ax.annotate(name, (x, y), fontsize=6.5, xytext=(4, 3), textcoords="offset points")
    if small and not is_route and (best_small is None or y > best_small["accuracy"]):
        best_small = r
if best_small:
    ax.annotate("best small model", (max(best_small["cost_per_1k_requests_usd"], 1e-4), best_small["accuracy"]),
                xytext=(-80, 25), textcoords="offset points", fontsize=9, fontweight="bold",
                arrowprops=dict(arrowstyle="->"))
ax.set_xscale("log")
ax.set_xlabel("cost per 1k requests (USD, log scale)")
ax.set_ylabel("set-level F1 on 180 held-out notes")
ax.set_title("Clinical note -> ICD-10-CM codes: quality vs. cost (Fireworks serverless)")
ax.grid(True, which="both", alpha=0.3)
fig.tight_layout()
fig.savefig(os.path.join(HERE, "frontier.png"), dpi=150)
print("saved frontier.png with", len(runs), "points")
