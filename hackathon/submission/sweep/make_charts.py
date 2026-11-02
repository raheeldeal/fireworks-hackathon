#!/usr/bin/env python3
"""Writes submission/frontier.png and submission/tokens.png.
Reads every sweep/results/*.json (stock configs + offline routing) and every submission/train/results/*.json with the same shape
(keys: model, tag, accuracy, cost_per_1k_requests_usd, in_tokens, out_tokens, reasoning_tokens, n). Tuned models are plotted in
orange automatically; while no train file exists the chart shows marked placeholders for "tuned, no catalog (SFT)" and "tuned (RFT)".
A train file may add "catalog_tokens": <int> (default 0, i.e. catalog-free) for the token chart."""
import json, glob, os, sys
import matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
HERE = os.path.dirname(os.path.abspath(__file__)); SUB = os.path.dirname(HERE)
CAT = json.load(open(os.path.join(HERE, "catalog_tokens.json")))
SHORT = {"nemotron-lightning-3p5-30b-a3b": "nemotron-30b-a3b", "glm-5p3-flash": "glm-5.3-flash", "deepseek-v4p1-flash": "deepseek-v4.1-flash",
         "gpt-oss-120b": "gpt-oss-120b", "glm-5p3": "glm-5.3", "kimi-k3": "kimi-k3"}
SMALL = {"nemotron-lightning-3p5-30b-a3b", "glm-5p3-flash"}
ORANGE, BLUE, GREY, RED, GREEN = "#e8710a", "#1f77b4", "#8c8c8c", "#d62728", "#2ca02c"

def load(pattern):
    out = []
    for p in sorted(glob.glob(pattern)):
        try: d = json.load(open(p))
        except Exception: continue
        if "accuracy" in d and "cost_per_1k_requests_usd" in d: d["_file"] = p; out.append(d)
    return out
stock = load(os.path.join(HERE, "results", "*.json"))
train_all = load(os.path.join(SUB, "train", "results", "*.json"))
# a train file with checkpoint "base" is the untuned base model (pipeline sanity check), not a tuned model
tuned = [d for d in train_all if str(d.get("checkpoint", "")).lower() not in ("base", "") or "tuned" in str(d.get("tag", "")).lower()]
untuned_base = [d for d in train_all if d not in tuned]

def kind_of(d):
    m = d["model"].split("/")[-1]
    if m.startswith("route"): return "route"
    if m in SMALL: return "small"
    if m == "kimi-k3": return "frontier"
    return "mid/large"
def tuned_kind(d):  # SFT vs RFT from tag/model/file name
    s = (d.get("tag", "") + d["model"] + os.path.basename(d["_file"])).lower()
    return "rft" if "rft" in s else "sft"
def nice_tag(tag):
    t = tag.replace("v1_plain", "plain").replace("v5_conf", "conf-json").replace("+mt512", " 512tok").replace("+mt4096", " 4096tok").replace("+rnone", " no-reason").replace("+rlow", " low-reason")
    return t

# ---------- frontier.png ----------
fig, ax = plt.subplots(figsize=(10, 6.5))
colors = {"small": BLUE, "mid/large": GREY, "frontier": RED, "route": GREEN}
names = {"small": "stock small model", "mid/large": "stock mid / large", "frontier": "frontier open (kimi-k3)", "route": "routing small -> large (offline)"}
for k in colors:
    sel = [d for d in stock if kind_of(d) == k]
    if sel: ax.scatter([d["cost_per_1k_requests_usd"] for d in sel], [d["accuracy"] for d in sel], c=colors[k], label=names[k], s=55, alpha=0.85, edgecolor="k", linewidth=0.5, zorder=3)
# annotate main table points + best small
for d in stock:
    m = d["model"].split("/")[-1]; k = kind_of(d)
    if k == "route":
        if abs(d.get("threshold", 0) - 0.9) > 1e-9: continue
        lbl = "route " + m[6:-1].replace("nemotron-lightning-3p5-30b-a3b", "nemotron").replace("glm-5p3-flash", "flash") + (" (self-conf)" if "self" in d.get("confidence_source", []) else " (logprob)") + f" @{d['threshold']}"
    elif d["tag"] in ("v1_plain", "v1_plain+rnone+mt512", "v1_plain+rlow+mt512"):
        lbl = f"{SHORT.get(m, m)} {nice_tag(d['tag'])}"
    else: continue
    ax.annotate(lbl, (d["cost_per_1k_requests_usd"], d["accuracy"]), fontsize=7, xytext=(5, 4), textcoords="offset points")
small = [d for d in stock if kind_of(d) == "small"]
if small:
    b = max(small, key=lambda d: (d["accuracy"], -d["cost_per_1k_requests_usd"]))
    ax.scatter([b["cost_per_1k_requests_usd"]], [b["accuracy"]], s=240, facecolors="none", edgecolors=BLUE, linewidths=2, zorder=4)
    ax.annotate(f"best stock small: {SHORT[b['model'].split('/')[-1]]} {nice_tag(b['tag'])}\n{b['accuracy']:.1%} at ${b['cost_per_1k_requests_usd']:.3f}/1k", (b["cost_per_1k_requests_usd"], b["accuracy"]), fontsize=8, fontweight="bold", xytext=(-150, -150), textcoords="offset points", arrowprops=dict(arrowstyle="->"))
# tuned models (orange) or placeholders
have = {tuned_kind(d) for d in tuned}
for d in tuned:
    ax.scatter([d["cost_per_1k_requests_usd"]], [d["accuracy"]], c=ORANGE, s=120, marker="*", edgecolor="k", linewidth=0.5, zorder=5)
for i, d in enumerate(tuned):
    ax.annotate(f"tuned ({tuned_kind(d).upper()}, no catalog): {os.path.basename(d['_file'])[:-5]}\n{d['accuracy']:.1%} at ${d['cost_per_1k_requests_usd']:.3f}/1k*", (d["cost_per_1k_requests_usd"], d["accuracy"]), fontsize=8, color=ORANGE, fontweight="bold", xytext=(8, 8 - 26 * i), textcoords="offset points")
if any("sampler" in str(d.get("pricing_note", "")) for d in tuned):
    ax.text(0.02, 0.10, "* tuned $/1k uses training-sampler rates (prefill $1.96/M, sample $4.88/M), not serving prices; see train/results pricing_note", transform=ax.transAxes, fontsize=7, color=ORANGE)
for j, d in enumerate(untuned_base):
    if d["accuracy"] >= 0.55:
        ax.scatter([d["cost_per_1k_requests_usd"]], [d["accuracy"]], facecolors="none", edgecolors=ORANGE, s=70, zorder=3)
        ax.annotate("base, no catalog (untuned)", (d["cost_per_1k_requests_usd"], d["accuracy"]), fontsize=7, color=ORANGE, xytext=(5, 4), textcoords="offset points")
    else:
        pass
offb = [d for d in untuned_base if d["accuracy"] < 0.55]
if offb: ax.text(0.02, 0.06, "off-chart: untuned base model with no catalog = " + ", ".join(f"{d['accuracy']:.0%} ({os.path.basename(d['_file'])})" for d in offb), transform=ax.transAxes, fontsize=7, color=ORANGE)
handles, labels = ax.get_legend_handles_labels()
if tuned: handles.append(Line2D([], [], marker="*", color="w", markerfacecolor=ORANGE, markeredgecolor="k", markersize=13)); labels.append("fine-tuned small model (train/results/)")
if "sft" not in have:
    handles.append(Line2D([], [], marker="*", color="w", markerfacecolor="none", markeredgecolor=ORANGE, markersize=13)); labels.append("tuned, no catalog (SFT): PLACEHOLDER, pending train/results/")
if "rft" not in have:
    handles.append(Line2D([], [], marker="*", color="w", markerfacecolor="none", markeredgecolor=ORANGE, markersize=13, linestyle=":")); labels.append("tuned (RFT): PLACEHOLDER, pending train/results/")

ax.legend(handles, labels, loc="lower right", fontsize=8)
ax.set_xscale("log"); ax.set_xlim(0.007, 12); ax.set_ylim(0.55, 1.005)
low = [d for d in stock if d["accuracy"] < 0.55]
if low: ax.text(0.02, 0.02, "below axis: " + ", ".join(f"{SHORT.get(d['model'].split('/')[-1], '')} {d['tag']} {d['accuracy']:.0%}" for d in low), transform=ax.transAxes, fontsize=7, color="gray")
ax.set_xlabel("cost per 1k requests (USD, log scale; serverless list prices, measured tokens)")
ax.set_ylabel("top-1 accuracy on the locked test set (180 rows; kimi-k3 first 100)")
ax.set_title("Tool routing over a 100-tool catalog: accuracy vs cost per call")
ax.grid(alpha=0.3, which="both"); fig.tight_layout(); fig.savefig(os.path.join(SUB, "frontier.png"), dpi=150)
print("frontier.png:", len(stock), "stock/route points,", len(tuned), "tuned points")

# ---------- tokens.png ----------
def breakdown(d, catalog_tokens):
    n = d["n"]; tin = d["in_tokens"] / n; tout = d["out_tokens"] / n; trs = d.get("reasoning_tokens", 0) / n
    return {"catalog": catalog_tokens, "request + instructions": max(tin - catalog_tokens, 0), "answer": max(tout - trs, 0), "reasoning": trs}
bars = []
by = {(d["model"].split("/")[-1], d["tag"]): d for d in stock}
for m, tag, name in [("glm-5p3-flash", "v1_plain", "glm-5.3-flash\nstock, default reasoning"), ("glm-5p3-flash", "v1_plain+rlow+mt512", "glm-5.3-flash\nstock, low reasoning"),
                     ("nemotron-lightning-3p5-30b-a3b", "v1_plain", "nemotron-30b-a3b\nstock, default reasoning"), ("nemotron-lightning-3p5-30b-a3b", "v1_plain+rnone+mt512", "nemotron-30b-a3b\nstock, reasoning off")]:
    if (m, tag) in by: bars.append((name, breakdown(by[(m, tag)], CAT[m]["catalog_tokens"]), False))
if tuned:
    seen = set()
    for d in tuned:  # one bar per distinct token profile (a re-scored copy of the same checkpoint adds nothing)
        key = (d["in_tokens"], d["out_tokens"])
        if key in seen: continue
        seen.add(key); bars.append((f"tuned ({tuned_kind(d).upper()}), no catalog\n{os.path.basename(d['_file'])[:-5]}", breakdown(d, d.get("catalog_tokens", 0)), True))
else:
    bars.append(("tuned, no catalog\n(PLACEHOLDER: pending\ntrain/results/)", {"catalog": 0, "request + instructions": 60, "answer": 8, "reasoning": 0}, True))
fig, ax = plt.subplots(figsize=(10, 5.5))
parts = ["catalog", "request + instructions", "reasoning", "answer"]; pc = {"catalog": "#4c72b0", "request + instructions": "#9ecae1", "reasoning": "#c7a5e8", "answer": "#55a868"}
x = range(len(bars)); bottom = [0] * len(bars)
for part in parts:
    vals = [b[1][part] for b in bars]
    ax.bar(x, vals, bottom=bottom, color=pc[part], label=part, edgecolor=[ORANGE if b[2] else "k" for b in bars], linewidth=[2 if b[2] else 0.5 for b in bars], hatch=["//" if (b[2] and not tuned) else "" for b in bars])
    bottom = [a + v for a, v in zip(bottom, vals)]
for i, (name, bd, is_t) in enumerate(bars):
    tot = sum(bd.values()); ax.text(i, tot + 20, f"{tot:.0f} tok/call" + ("" if tot and not (is_t and not tuned) else " (placeholder)"), ha="center", fontsize=8, color=ORANGE if is_t else "k", fontweight="bold" if is_t else "normal")
    if bd["catalog"]: ax.text(i, bd["catalog"] / 2, f"catalog\n{bd['catalog']/tot:.0%} of tokens", ha="center", va="center", fontsize=8, color="w")
ax.set_xticks(list(x)); ax.set_xticklabels([b[0] for b in bars], fontsize=8)
ax.set_ylabel("tokens per call (mean over the locked test set)"); ax.set_title("Where the tokens go: the catalog dominates every stock call")
ax.legend(loc="upper right", fontsize=8); ax.grid(axis="y", alpha=0.3); fig.tight_layout(); fig.savefig(os.path.join(SUB, "tokens.png"), dpi=150)
print("tokens.png:", len(bars), "bars")
