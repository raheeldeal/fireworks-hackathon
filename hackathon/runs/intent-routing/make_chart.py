#!/usr/bin/env python3
"""frontier.png: x = $ per 1k requests (log), y = accuracy. One point per results/*.json config plus routing sweep points.
Labels the best small-model point. Usage: python3 make_chart.py [--best results/<file>.json]"""
import argparse, glob, json, os
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

HERE = os.path.dirname(os.path.abspath(__file__))
SMALL = ("nemotron-lightning-3p5-30b-a3b", "glm-5p3-flash")
ap = argparse.ArgumentParser(); ap.add_argument("--best", help="results json of the best small config to label")
ap.add_argument("--out", default=os.path.join(HERE, "frontier.png"))
ap.add_argument("--routes", default="", help="comma-separated routing_*.json basenames to draw (default: all)"); a = ap.parse_args()

pts = []
for p in sorted(glob.glob(os.path.join(HERE, "results", "*.json"))):
    d = json.load(open(p))
    if "rows" not in d or d.get("seed"):  # skip routing files and seed re-runs (variance reported in table)
        continue
    if any(r["error"] for r in d["rows"]):
        continue  # incomplete run
    m = d["model"].split("/")[-1]
    pts.append({"x": d["cost_per_1k_requests_usd"], "y": d["accuracy"], "name": f"{m}\n{d['prompt']}", "small": m in SMALL,
                "frontier": m == "kimi-k3", "best": a.best and os.path.abspath(p) == os.path.abspath(a.best)})
routes = []
want = [x for x in a.routes.split(",") if x]
for p in sorted(glob.glob(os.path.join(HERE, "results", "routing_*.json"))):
    if want and os.path.basename(p)[:-5] not in want:
        continue
    d = json.load(open(p))
    routes.append((os.path.basename(p)[8:-5].replace("__", " → "), d["sweep"]))

fig, ax = plt.subplots(figsize=(9, 6))
for s in pts:
    c = "#d62728" if s["frontier"] else ("#1f77b4" if s["small"] else "#7f7f7f")
    ax.scatter(s["x"], s["y"], s=120 if s["best"] else 50, c=c, edgecolor="k" if s["best"] else "none", zorder=3)
    ax.annotate(s["name"], (s["x"], s["y"]), fontsize=6.5, xytext=(4, 4), textcoords="offset points")
for name, sweep in routes:
    xs = [r["cost_per_1k_requests_usd"] for r in sweep]; ys = [r["accuracy"] for r in sweep]
    ax.plot(xs, ys, "-o", ms=3, lw=1, alpha=0.8, label=f"routing: {name}")
    for r in sweep:
        ax.annotate(f"t={r['threshold']:.2f}", (r["cost_per_1k_requests_usd"], r["accuracy"]), fontsize=5, xytext=(2, -8), textcoords="offset points")
ax.set_xscale("log"); ax.set_xlabel("$ per 1k requests (log)"); ax.set_ylabel("accuracy (154-row Banking77 test, 77 intents)")
ax.set_title("Banking intent routing: accuracy vs. cost\nblue = small models, grey = medium/large, red = frontier (kimi-k3, 100 rows)")
ax.grid(True, which="both", alpha=0.3)
if routes:
    ax.legend(fontsize=7, loc="lower right")
fig.tight_layout(); fig.savefig(a.out, dpi=150); print("saved", a.out, len(pts), "points,", len(routes), "routing curves")
