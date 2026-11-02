#!/usr/bin/env python3
"""Slide-ready waterfall charts (1920x1080 PNG) for the text-to-Cypher pitch.

Every number is read from the per-question result files, never typed in.
  python3 make_waterfall.py              # strict scorer v1 (hackathon/cypher/results/)
  python3 make_waterfall.py --scorer v2  # strict scorer v2 (results_v2/, used by RESULTS_FINAL.md)
Lenient scores are identical in both folders.

Rules the charts follow:
  * strict and lenient never share a chart
  * the fine-tune lane (Muse Glimmer 30B) is never stacked on the harness lane (GLM 5.3 Flash)
  * Claude Opus 5 is a reference line or bar, not a step
  * harness steps are single runs (run-to-run noise is about +/-2pp)
"""
import json, os, sys
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle

HERE = os.path.dirname(os.path.abspath(__file__))
SCORER = "v2" if "--scorer" in sys.argv and sys.argv[sys.argv.index("--scorer") + 1] == "v2" else "v1"
RES = os.path.join(HERE, "..", "results_v2" if SCORER == "v2" else "results")
SUFFIX = "_v2" if SCORER == "v2" else ""

def score(f, metric):
    d = json.load(open(os.path.join(RES, f)))
    rows = d["rows"]
    if metric == "strict":
        acc = sum(bool(r["correct"]) for r in rows) / len(rows)
        assert abs(acc - d["accuracy"]) < 1e-9, f"{f}: recomputed {acc} != stored {d['accuracy']}"
    else:
        acc = d["accuracy_lenient"]
    return round(acc * 100, 1), d["n"], d.get("cost_per_1k_requests_usd")

# ---- data -------------------------------------------------------------------
HARNESS = [  # (label, file, what it catches)
    ("GLM 5.3 Flash\n(open, small)", "harness_validate_only.json", None),
    ("+ Repair", "harness_repair1.json",
     "Crashed queries.\n\u201cAvg rating of\nMatrix movies\u201d\nnow runs"),
    ("+ Vote of 3", "harness_vote3.json",
     "Hard multi-hop.\n\u201c3 directors in\n3+ genres\u201d"),
    ("+ Route on\ndisagreement", "harness_route_big.json",
     "The 6% where\ntries disagree.\n\u201cUsers who rated\nevery genre\u201d"),
]
FINETUNE = [
    ("Muse 30B\n(open, base)", "train_base.json", None),
    ("+ SFT", "train_sft.json", "Empty results. “Who interacts\nmost with ‘neo4j’?”"),
    ("+ RFT", "train_rft_r1_reject.json", "Recency, top-N.\n“3 most recent tweets”"),
]
CLAUDE = "claude-opus-5_v1_plain_n100.json"
AUDIT = [  # 40 hand-audited misses of the best small model (RESULTS_FINAL.md, audit/)
    ("Broken answer key", 11), ("Ambiguous question", 7),
    ("Right answer,\nother column", 20), ("Model truly wrong", 2),
]

def lane(spec, metric):
    return [(lab, *score(f, metric), ex) for lab, f, ex in spec]

# ---- style ------------------------------------------------------------------
INK, MUTED, GRID = "#1d1d1f", "#6e6e73", "#e5e5ea"
BLUE, BLUE_L = "#1f5fbf", "#8fb3e8"
ORANGE, ORANGE_L = "#c2571a", "#f0b48a"
GREY = "#9a9aa0"
AUDIT_C = ["#d9534f", "#e8a33d", "#9b7fd1", "#3a3a3c"]
plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 20, "axes.edgecolor": GRID,
                     "axes.spines.top": False, "axes.spines.right": False})

def new_fig():
    return plt.figure(figsize=(19.2, 10.8), dpi=100, facecolor="white")

def title(fig, t, sub):
    fig.text(0.04, 0.93, t, fontsize=44, weight="bold", color=INK)
    fig.text(0.04, 0.885, sub, fontsize=20, color=MUTED)

def footnote(fig, t):
    fig.text(0.04, 0.02, t, va="bottom", linespacing=1.4, fontsize=15, color=MUTED)

def waterfall(ax, data, dark, light, ymax=80, examples=False, single_run=False, label_size=19):
    """First bar solid from 0, each step a floating block, final total outlined."""
    xs = range(len(data))
    prev = None
    for i, (lab, acc, n, cost, ex) in enumerate(data):
        if prev is None:
            ax.bar(i, acc, 0.62, color=dark)
            ax.text(i, acc + 1.2, f"{acc:.1f}%", ha="center", va="bottom", fontsize=26, weight="bold", color=INK)
        else:
            d = acc - prev
            lo = min(acc, prev)
            ax.bar(i, prev if d >= 0 else acc, 0.62, color=light, alpha=0.35)  # carried level
            ax.bar(i, abs(d), 0.62, bottom=lo, color=dark if d >= 0 else "#d9534f")
            ax.plot([i - 1 + 0.31, i - 0.31], [prev, prev], color=MUTED, lw=1.5, ls=":")
            ax.text(i, acc + 5.0, f"{'+' if d >= 0 else ''}{d:.1f}", ha="center", va="bottom",
                    fontsize=26, weight="bold", color=dark)
            ax.text(i, acc + 1.0, f"= {acc:.1f}%", ha="center", va="bottom", fontsize=17, color=INK)
            if single_run:
                ax.text(i, -0.5, "single run", ha="center", va="top", fontsize=13, color=MUTED,
                        style="italic", transform=ax.get_xaxis_transform() if False else ax.transData)
        prev = acc
    ax.set_xticks(list(xs))
    ax.set_xticklabels([d[0] for d in data], fontsize=label_size, color=INK)
    ax.set_ylim(0, ymax)
    ax.set_yticks(range(0, ymax + 1, 20))
    ax.set_yticklabels([f"{v}%" for v in range(0, ymax + 1, 20)], fontsize=16, color=MUTED)
    ax.grid(axis="y", color=GRID, lw=1)
    ax.set_axisbelow(True)
    ax.tick_params(length=0)
    if examples:
        for i, (lab, acc, n, cost, ex) in enumerate(data):
            if ex:
                ax.text(i, -0.2, ex, ha="center", va="top", fontsize=15, color=MUTED,
                        transform=ax.get_xaxis_transform(), linespacing=1.3)

def claude_line(ax, acc, cost, xmax, text=True):
    ax.axhline(acc, color=GREY, ls="--", lw=2.5, zorder=0)
    if text:
        ax.text(0.99, 0.97, f"- - -  Claude Opus 5 (frontier): {acc:.0f}%, ${cost:.2f} / 1k q", ha="right",
                va="top", fontsize=17, color=MUTED, transform=ax.transAxes)

def save(fig, name):
    p = os.path.join(HERE, f"{name}{SUFFIX}.png")
    fig.savefig(p, dpi=100, facecolor="white")
    plt.close(fig)
    print("wrote", os.path.relpath(p, os.getcwd()))

SCORE_NOTE = {"v1": "strict scorer", "v2": "strict scorer v2"}[SCORER]

# ---- version 1: strict, two lanes --------------------------------------------
def v1():
    h, f = lane(HARNESS, "strict"), lane(FINETUNE, "strict")
    c_acc, c_n, c_cost = score(CLAUDE, "strict")
    fig = new_fig()
    title(fig, "Two ways to beat the frontier with open models",
          f"Execution accuracy, {SCORE_NOTE}: exact rows from the live Neo4j graph. 200 held-out questions.")
    ax1 = fig.add_axes([0.06, 0.17, 0.50, 0.62])
    ax2 = fig.add_axes([0.62, 0.17, 0.35, 0.62])
    waterfall(ax1, h, BLUE, BLUE_L, single_run=False)
    waterfall(ax2, f, ORANGE, ORANGE_L)
    claude_line(ax1, c_acc, c_cost, 3.4)
    claude_line(ax2, c_acc, c_cost, 2.4, text=False)
    ax1.set_title("Harness lane  ·  GLM 5.3 Flash", fontsize=24, color=BLUE, loc="left", weight="bold", pad=16)
    ax2.set_title("Fine-tune lane  ·  Muse Glimmer 30B", fontsize=24, color=ORANGE, loc="left", weight="bold", pad=16)
    footnote(fig, f"Separate models: the lanes are not stacked. Harness steps are single runs (run-to-run noise ≈ ±2pp).\n"
                  f"SFT held across 3 seeds. Claude Opus 5 ran on the first {c_n} questions only.")
    save(fig, "v1_strict_two_lanes")

# ---- version 2: lenient, two lanes -------------------------------------------
def v2():
    h, f = lane(HARNESS, "lenient"), lane(FINETUNE, "lenient")
    fig = new_fig()
    title(fig, "Two ways to beat the frontier with open models",
          "Execution accuracy, lenient scorer: right rows, extra columns allowed. 200 held-out questions.")
    ax1 = fig.add_axes([0.06, 0.17, 0.50, 0.62])
    ax2 = fig.add_axes([0.62, 0.17, 0.35, 0.62])
    waterfall(ax1, h, BLUE, BLUE_L)
    waterfall(ax2, f, ORANGE, ORANGE_L)
    ax1.set_title("Harness lane  ·  GLM 5.3 Flash", fontsize=24, color=BLUE, loc="left", weight="bold", pad=16)
    ax2.set_title("Fine-tune lane  ·  Muse Glimmer 30B", fontsize=24, color=ORANGE, loc="left", weight="bold", pad=16)
    footnote(fig, "Claude Opus 5 has no lenient score, so it is not shown. Separate models: the lanes are not stacked. "
                  "Harness steps are single runs (noise ≈ ±2pp).")
    save(fig, "v2_lenient_two_lanes")

# ---- version 3: classic single waterfall + fine-tune side panel ----------------
def v3():
    h, f = lane(HARNESS, "strict"), lane(FINETUNE, "strict")
    c_acc, c_n, c_cost = score(CLAUDE, "strict")
    data = [("Claude Opus 5\n(frontier)", c_acc, c_n, c_cost, f"Reference.\n${c_cost:.2f} / 1k q.\nFirst {c_n} q only")] + h
    fig = new_fig()
    title(fig, f"From {h[0][1]:.0f}% to {h[-1][1]:.0f}%: what each step catches",
          f"Execution accuracy, {SCORE_NOTE}. 200 held-out questions on live Neo4j graphs.")
    ax = fig.add_axes([0.06, 0.30, 0.60, 0.50])
    # Claude reference bar, then the harness waterfall shifted right by one slot
    ax.bar(0, c_acc, 0.62, color=GREY, hatch="//", edgecolor="white")
    ax.text(0, c_acc + 1.2, f"{c_acc:.0f}%", ha="center", va="bottom", fontsize=26, weight="bold", color=MUTED)
    ax.axvline(0.6, color=GRID, lw=2)
    sub = fig.add_axes([0.06, 0.30, 0.60, 0.50], sharey=ax)
    sub.set_visible(False)
    prev = None
    for i, (lab, acc, n, cost, ex) in enumerate(h, start=1):
        if prev is None:
            ax.bar(i, acc, 0.62, color=BLUE)
            ax.text(i, acc + 1.2, f"{acc:.0f}%", ha="center", va="bottom", fontsize=26, weight="bold", color=INK)
            ax.text(i, -0.2, f"${cost:.2f} / 1k q", ha="center", va="top", fontsize=14, color=MUTED,
                    transform=ax.get_xaxis_transform())
        else:
            ax.bar(i, prev, 0.62, color=BLUE_L, alpha=0.35)
            ax.bar(i, acc - prev, 0.62, bottom=prev, color=BLUE)
            ax.plot([i - 1 + 0.31, i - 0.31], [prev, prev], color=MUTED, lw=1.5, ls=":")
            ax.text(i, acc + 1.2, f"+{acc - prev:.0f}", ha="center", va="bottom", fontsize=26, weight="bold", color=BLUE)
            ax.text(i, -0.2, ex, ha="center", va="top", fontsize=15, color=MUTED,
                    transform=ax.get_xaxis_transform(), linespacing=1.3)
        prev = acc
    i = len(h) + 1
    ax.bar(i, prev, 0.62, color="white", edgecolor=BLUE, lw=3)
    ax.text(i, prev + 1.2, f"{prev:.0f}%", ha="center", va="bottom", fontsize=30, weight="bold", color=BLUE)
    ax.text(0, -0.2, data[0][4], ha="center", va="top", fontsize=14, color=MUTED,
            transform=ax.get_xaxis_transform(), linespacing=1.3)
    ax.set_xticks(range(len(h) + 2))
    ax.set_xticklabels([data[0][0]] + [x[0] for x in h] + ["Harness\ntotal"], fontsize=17, color=INK)
    ax.set_ylim(0, 70); ax.set_yticks(range(0, 71, 20))
    ax.set_yticklabels([f"{v}%" for v in range(0, 71, 20)], fontsize=16, color=MUTED)
    ax.grid(axis="y", color=GRID); ax.set_axisbelow(True); ax.tick_params(length=0)
    ax.tick_params(axis="x", pad=10)
    # side panel: fine-tune lane
    fig.patches.append(Rectangle((0.70, 0.12), 0.27, 0.72, transform=fig.transFigure,
                                 facecolor="#fbf4ee", edgecolor="none", zorder=-1))
    fig.text(0.72, 0.80, "Separately: fine-tuning", fontsize=24, weight="bold", color=ORANGE)
    fig.text(0.72, 0.765, "Muse Glimmer 30B, a different open model", fontsize=15, color=MUTED)
    ax2 = fig.add_axes([0.74, 0.30, 0.21, 0.42])
    waterfall(ax2, f, ORANGE, ORANGE_L, ymax=70, label_size=15)
    for t in ax2.texts:
        t.set_fontsize(min(t.get_fontsize(), 20))
    ax2.set_yticklabels([])
    fig.text(0.72, 0.205, f"SFT: +{f[1][1]-f[0][1]:.1f}, held across 3 seeds.\n"
                          f"RFT: +{f[2][1]-f[1][1]:.1f}, reward = database\nreturns the right rows.",
             fontsize=15, color=INK, va="top", linespacing=1.4)
    footnote(fig, "Harness steps are single runs (run-to-run noise ≈ ±2pp). The lanes use different models and are not stacked.")
    save(fig, "v3_classic_waterfall")

# ---- version 4: build-up to the ceiling ---------------------------------------
def v4(frames=True):
    """Harness lane on the left; on the right, the 100% bar split into what we got
    and why the rest is missing, estimated from the 40-miss audit. Also writes
    step-by-step frames so the slide can build in the video."""
    h = lane(HARNESS, "strict")
    c_acc, c_n, c_cost = score(CLAUDE, "strict")
    final = h[-1][1]
    total_audit = sum(n for _, n in AUDIT)

    def draw(step):
        fig = new_fig()
        title(fig, "Why we stop at %.0f%%: the exam, not the model" % final if step >= len(h) + 1
              else "Building past the frontier, one step at a time",
              f"Execution accuracy, {SCORE_NOTE}. 200 held-out questions on live Neo4j graphs.")
        ax = fig.add_axes([0.06, 0.20, 0.55, 0.60])
        prev = None
        for i, (lab, acc, n, cost, ex) in enumerate(h):
            if i > step:
                break
            if prev is None:
                ax.bar(i, acc, 0.62, color=BLUE)
                ax.text(i, acc + 1.2, f"{acc:.0f}%", ha="center", va="bottom", fontsize=28, weight="bold", color=INK)
            else:
                ax.bar(i, prev, 0.62, color=BLUE_L, alpha=0.35)
                ax.bar(i, acc - prev, 0.62, bottom=prev, color=BLUE)
                ax.plot([i - 1 + 0.31, i - 0.31], [prev, prev], color=MUTED, lw=1.5, ls=":")
                ax.text(i, acc + 1.2, f"+{acc - prev:.0f}", ha="center", va="bottom", fontsize=28, weight="bold", color=BLUE)
                ax.text(i, -0.17, ex.replace("\n", " ").split(". ")[0], ha="center", va="top",
                        fontsize=15, color=MUTED, transform=ax.get_xaxis_transform())
            prev = acc
        claude_line(ax, c_acc, c_cost, len(h) - 0.6)
        ax.set_xlim(-0.6, len(h) - 0.4)
        ax.set_xticks(range(len(h)))
        ax.set_xticklabels([x[0] if i <= step else "" for i, x in enumerate(h)], fontsize=18, color=INK)
        ax.set_ylim(0, 100); ax.set_yticks(range(0, 101, 25))
        ax.set_yticklabels([f"{v}%" for v in range(0, 101, 25)], fontsize=16, color=MUTED)
        ax.grid(axis="y", color=GRID); ax.set_axisbelow(True); ax.tick_params(length=0)
        if step >= len(h) + 1:
            axc = fig.add_axes([0.70, 0.20, 0.08, 0.60])
            axc.bar(0, final, 0.8, color=BLUE)
            axc.text(0, final / 2, f"{final:.0f}%\nright", ha="center", va="center", color="white", fontsize=20, weight="bold")
            bottom = final
            for (lab, n), col in zip(AUDIT, AUDIT_C):
                share = (100 - final) * n / total_audit
                axc.bar(0, share, 0.8, bottom=bottom, color=col)
                fig.text(0.79, 0.20 + 0.60 * (bottom + share / 2) / 100, f"{lab}  ({n}/{total_audit})",
                         va="center", fontsize=18, color=INK)
                bottom += share
            axc.set_ylim(0, 100); axc.axis("off")
            fig.text(0.70, 0.83, "The missing %.0f%%" % (100 - final), fontsize=24, weight="bold", color=INK)
            fig.text(0.70, 0.13, f"Split estimated from {total_audit} hand-audited misses.\n"
                                 f"Only {AUDIT[-1][1]} of {total_audit} were the model’s fault.",
                     fontsize=16, color=MUTED, va="top", linespacing=1.4)
        footnote(fig, f"Harness steps are single runs (noise ≈ ±2pp). Claude Opus 5 ran on the first {c_n} questions only.")
        return fig

    last = len(h) + 1
    if frames:
        os.makedirs(os.path.join(HERE, "frames"), exist_ok=True)
        for s in range(last + 1):
            if s == len(h):
                continue  # identical to the step before the ceiling appears
            fig = draw(s)
            p = os.path.join(HERE, "frames", f"v4_step{s}{SUFFIX}.png")
            fig.savefig(p, dpi=100, facecolor="white"); plt.close(fig)
        print("wrote", os.path.relpath(os.path.join(HERE, "frames"), os.getcwd()), "(build frames)")
    save(draw(last), "v4_buildup_ceiling")

if __name__ == "__main__":
    v1(); v2(); v3(); v4()
