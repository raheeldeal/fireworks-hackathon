#!/usr/bin/env python3
"""frontier.png: x = $ per 1k requests (log), y = execution accuracy, one point per configuration."""
import glob, json, os, sys
import matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt
HERE = os.path.dirname(os.path.abspath(__file__))
paths = sys.argv[1:] or sorted(glob.glob(os.path.join(HERE, "results", "*.json")))
import re
runs = [json.load(open(p)) for p in paths if "seed" not in os.path.basename(p) and not os.path.basename(p).startswith(("scratch", "sft_job"))
        and (not os.path.basename(p).startswith("route_") or re.search(r"th-1\.0\.json$", p))]
fig, ax = plt.subplots(figsize=(11, 7))
best_small = None
for i, r in enumerate(sorted(runs, key=lambda r: r["cost_per_1k_requests_usd"])):
    name = r["model"].split("/")[-1].replace("accounts/fireworks/models/", "")
    short = lambda m: m.replace("nemotron-lightning-3p5-30b-a3b", "nemotron-30b").replace("deepseek-v4p1-flash", "deepseek-flash").replace("muse-glimmer-30b", "muse-30b")
    if name.startswith("route"):
        a, b = re.match(r"route\[(.*)->(.*)\]", name).groups()
        label = f"route {short(a)}→{short(b)} (escalate invalid)"
    else:
        label = f"{short(name)} + {r['prompt'].replace('_lp','').replace('v1_plain','plain').replace('v2_rubric','rubric').replace('v3_fewshot','5-shot').replace('_nothink',' no-think').replace('_json',' json')}"
    if r["prompt"] == "v1_plain_lp":
        continue  # duplicate of the plain run, kept only for routing
    x, y = max(r["cost_per_1k_requests_usd"], 1e-4), r["accuracy"] * 100
    kind = "route" if name.startswith("route") else ("frontier" if "kimi" in name or name == "glm-5p3" else ("sft" if "sft" in label else "small"))
    color = {"route": "#d97706", "frontier": "#6b7280", "sft": "#059669", "small": "#2563eb"}[kind]
    ax.scatter(x, y, s=70, color=color, zorder=3)
    ax.annotate(label, (x, y), textcoords="offset points", xytext=(6, 4 if i % 2 == 0 else -10), fontsize=7)
    if kind in ("small", "sft", "route") and (best_small is None or y > best_small[1]):
        best_small = (x, y, label)
if best_small:
    ax.scatter([best_small[0]], [best_small[1]], s=260, facecolors="none", edgecolors="#dc2626", linewidths=2, zorder=4)
    ax.annotate("best small-model config", best_small[:2], textcoords="offset points", xytext=(-150, 10), fontsize=8, color="#dc2626")
ax.set_xscale("log"); ax.set_xlabel("cost per 1k requests (USD, log scale)"); ax.set_ylabel("execution accuracy (%)")
ax.set_title("Text-to-SQL (Spider dev, 180 questions, 20 schemas): accuracy vs. cost")
ax.grid(True, which="both", alpha=0.3)
plt.tight_layout(); plt.savefig(os.path.join(HERE, "frontier.png"), dpi=150)
print("saved frontier.png with", len(runs), "points")
