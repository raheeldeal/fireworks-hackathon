#!/usr/bin/env python3
"""frontier.png: x = $ per 1k requests (log), y = accuracy; one point per config; best small-model point labelled."""
import json, glob, os, collections
import matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt
HERE = os.path.dirname(os.path.abspath(__file__))
SMALL = {"nemotron-lightning-3p5-30b-a3b", "glm-5p3-flash"}
groups = collections.defaultdict(list)
for p in glob.glob(os.path.join(HERE, "results", "*.json")):
    d = json.load(open(p)); groups[(d["model"], d.get("tag", d["prompt"]))].append(d)
pts = []
for (model, tag), ds in groups.items():
    acc = sum(d["accuracy"] for d in ds) / len(ds); cost = sum(d["cost_per_1k_requests_usd"] for d in ds) / len(ds)
    if cost <= 0: continue
    m = model.split("/")[-1]
    kind = "route" if m.startswith("route") else ("small" if m in SMALL else ("frontier" if m == "kimi-k3" else "mid/large"))
    pts.append((cost, acc, m, tag, kind))
colors = {"small": "#1f77b4", "mid/large": "#7f7f7f", "frontier": "#d62728", "route": "#2ca02c"}
fig, ax = plt.subplots(figsize=(9, 6))
for kind in colors:
    sel = [p for p in pts if p[4] == kind]
    if sel: ax.scatter([p[0] for p in sel], [p[1] for p in sel], c=colors[kind], label=kind, s=60, alpha=0.85, edgecolor="k", linewidth=0.5)
SHORT = {"nemotron-lightning-3p5-30b-a3b": "nemotron", "glm-5p3-flash": "glm-flash", "deepseek-v4p1-flash": "deepseek-flash", "gpt-oss-120b": "gpt-oss", "glm-5p3": "glm-5p3", "kimi-k3": "kimi-k3"}
def label(m, tag):
    if m.startswith("route"): return "route " + m[6:-1].replace("nemotron-lightning-3p5-30b-a3b", "nemotron").replace("glm-5p3-flash", "glm-flash") + " " + tag.split("@")[1]
    return f"{SHORT.get(m, m)} {tag}"
LABEL = {("v1_plain",), ("v1_plain+rnone",), ("v1_plain+rlow",), ("v1_plain+retr10",), ("v2_rubric+rnone",), ("v1_plain+5shot",)}
for cost, acc, m, tag, kind in pts:
    if kind == "route" and tag not in ("route@-0.1",): continue
    if kind != "route" and (tag,) not in LABEL: continue
    ax.annotate(label(m, tag), (cost, acc), fontsize=7, xytext=(4, 4), textcoords="offset points")
ax.set_ylim(0.55, 1.01)
low = [p for p in pts if p[1] < 0.55]
if low: ax.text(0.02, 0.03, "below axis: " + ", ".join(f"{SHORT.get(p[2], p[2])} {p[3]} {p[1]:.0%}" for p in low), transform=ax.transAxes, fontsize=7, color="gray")
small = [p for p in pts if p[4] == "small"]
if small:
    b = max(small, key=lambda p: (p[1], -p[0]))
    ax.scatter([b[0]], [b[1]], s=260, facecolors="none", edgecolors="#1f77b4", linewidths=2)
    ax.annotate(f"best small: {b[2]} {b[3]}\n{b[1]:.1%} at ${b[0]:.3f}/1k", (b[0], b[1]), fontsize=8, fontweight="bold", xytext=(10, -28), textcoords="offset points", arrowprops=dict(arrowstyle="->"))
ax.set_xscale("log"); ax.set_xlabel("cost per 1k requests (USD, log scale)"); ax.set_ylabel("top-1 accuracy (180-row test set)")
ax.set_title("Tool selection over a 100-tool catalog: accuracy vs cost"); ax.grid(alpha=0.3, which="both"); ax.legend(loc="lower right")
fig.tight_layout(); fig.savefig(os.path.join(HERE, "frontier.png"), dpi=150); print("saved frontier.png with", len(pts), "points")
