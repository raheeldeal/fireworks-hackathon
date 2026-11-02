#!/usr/bin/env python3
"""frontier.png: x = cost per 1k requests (log), y = strict accuracy; one point per configuration.
Reads every results/*.json (run_eval summaries and route sweeps). Labels the best small-model point.
  python3 frontier.py [--label-all]"""
import glob, json, os, re, sys, statistics
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

HERE = os.path.dirname(os.path.abspath(__file__))
SMALL = ("nemotron-lightning-3p5-30b-a3b", "glm-5p3-flash", "muse", "sft")
pts = []
groups = {}   # config stem (seeds merged) -> list of (cost, acc)
for p in sorted(glob.glob(os.path.join(HERE, "results", "*.json"))):
    d = json.load(open(p))
    stem = os.path.basename(p)[:-5]
    if isinstance(d, list):                      # route sweep: one point per pair, the best-accuracy threshold
        r = max(d, key=lambda r: (r["accuracy"], -r["cost_per_1k_requests_usd"]))
        short = stem.replace("route_", "").replace("_tools_v1_plain", "").replace("_to_", " -> ")
        pts.append((r["cost_per_1k_requests_usd"], r["accuracy"], f"route {short} thr={r['threshold']} esc {r['escalated_frac']:.0%}", "route", r.get("n", 0)))
        continue
    if "accuracy" not in d or d.get("n", 0) < 50 or stem.startswith("smoke"):
        continue
    kind = "small" if any(s in d["model"] for s in SMALL) else ("frontier" if "kimi" in d["model"] else "other")
    groups.setdefault(re.sub(r"_seed\d+$", "", stem), {"kind": kind, "n": d["n"], "v": []})["v"].append((d["cost_per_1k_requests_usd"], d["accuracy"]))
for stem, g in groups.items():
    pts.append((statistics.mean(c for c, _ in g["v"]), statistics.mean(a for _, a in g["v"]), stem + (f" (mean of {len(g['v'])})" if len(g["v"]) > 1 else ""), g["kind"], g["n"]))
if not pts:
    sys.exit("no results to plot")
colors = {"small": "#1f77b4", "other": "#7f7f7f", "frontier": "#d62728", "route": "#2ca02c"}
markers = {"small": "o", "other": "s", "frontier": "*", "route": "^"}
fig, ax = plt.subplots(figsize=(9, 6))
for kind in colors:
    sel = [p for p in pts if p[3] == kind]
    if sel:
        ax.scatter([p[0] for p in sel], [p[1] for p in sel], c=colors[kind], marker=markers[kind], s=70 if kind != "frontier" else 160, label=kind, alpha=0.85)
smalls = [p for p in pts if p[3] == "small"]
top = max(p[1] for p in smalls) if smalls else 0
# "best small" = cheapest small point within 1 point of the best small accuracy (Pareto corner)
best_small = min((p for p in smalls if p[1] >= top - 0.01), key=lambda p: p[0], default=None)
label_all = "--label-all" in sys.argv
def short(name):
    name = name.replace("_v1_plain", "").replace("nemotron-lightning-3p5-30b-a3b", "nemotron").replace(" (mean of", " (x")
    if name.startswith("route "):   # "route A -> B thr=-0.01 esc 31%" -> "route A->B esc 31%"
        name = re.sub(r" thr=\S+", "", name).replace(" -> ", "->").replace("_relow", "").replace("glm-5p3-flash", "flash")
    return name
for p in pts:
    if p is best_small:
        ax.annotate(f"best small: {short(p[2])}\n{p[1]:.1%} @ ${p[0]:.3f}/1k", (p[0], p[1]), textcoords="offset points", xytext=(15, -60), fontsize=8,
                    arrowprops=dict(arrowstyle="->", lw=0.8), bbox=dict(boxstyle="round", fc="lightyellow"))
    elif label_all or p[3] in ("frontier", "other") or (p[3] == "small" and (p[1] >= 0.885 or "muse" in p[2] or "sft" in p[2])) or (p[3] == "route" and p[1] >= 0.9):
        ax.annotate(short(p[2]), (p[0], p[1]), textcoords="offset points", xytext=(5, 4), fontsize=6)
ax.set_xscale("log")
ax.set_xlabel("cost per 1k requests (USD, log scale)")
ax.set_ylabel("strict accuracy (name + all arguments)")
ax.set_title("Function calling on BFCL v4 (200-row locked test): quality vs. cost")
ax.grid(True, which="both", alpha=0.3)
ax.legend(loc="center right")
fig.tight_layout()
fig.savefig(os.path.join(HERE, "frontier.png"), dpi=150)
print(f"plotted {len(pts)} points -> frontier.png; best small = {best_small[2] if best_small else None}")
