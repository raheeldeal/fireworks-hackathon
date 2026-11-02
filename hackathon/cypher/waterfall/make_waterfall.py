#!/usr/bin/env python3
"""Slide-ready waterfall charts (1920x1080 PNG) of the cumulative improvement ladder.

  python3 build_ladder.py --data <folder>   # recompute ladder.json from the per-question result files
  python3 make_waterfall.py                 # draw the charts from ladder.json

One system, built up in order: untuned Muse Glimmer 30B, then four harness steps, then SFT inside the harness.
Every step is measured against the step before it on the same questions. Claude Sonnet 4.6 is a published number
on a different subset, so it is drawn as a reference line, never as a step.
"""
import json, os
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle

HERE = os.path.dirname(os.path.abspath(__file__))
LAD = json.load(open(os.path.join(HERE, "ladder.json")))
FR = LAD["frontier_reference"]

# what kind of question each step newly gets right, with a real example from the run (ladder.json "examples")
CATCH = {
    "Retrieved examples": ("Graph vocabulary", "“Top 3 filings where\nthe bank country\nis Singapore”"),
    "Arrow-direction fix": ("Wrong arrows", "“Which users reply\nto each other\nmost?”"),
    "Repair loop": ("Crashed queries", "“Avg votes for movies\nfrom the year Speed\nRacer came out”"),
    "Escalate to Kimi K3": ("Hard multi-hop", "“Pair of directors\nsharing the\nmost actors”"),
    "SFT": ("Conventions", "“Top 5 users\n‘Neo4j’ interacts\nwith”"),
    "More SFT data": ("Wider coverage", "“Avg rating of\n‘The Matrix’\nmovies”"),
}
SHORT = {"Untuned open model": "Muse 30B\nuntuned", "Retrieved examples": "+ Retrieved\nexamples",
         "Arrow-direction fix": "+ Arrow\nfix", "Repair loop": "+ Repair\nloop",
         "Escalate to Kimi K3": "+ Escalate\nto Kimi K3", "SFT": "+ SFT", "More SFT data": "+ More\nSFT data"}

INK, MUTED, GRID = "#1d1d1f", "#6e6e73", "#e5e5ea"
START_C, HARN, HARN_L, TUNE, TUNE_L, TOTAL = "#3a3a3c", "#1f5fbf", "#d6e2f5", "#c2571a", "#f6dccb", "#111111"
REASON_C = {"model_wrong": "#3a3a3c", "format_only": "#9b7fd1", "ambiguous": "#e8a33d", "gold_wrong": "#d9534f"}
REASON_L = {"model_wrong": "Model truly wrong", "format_only": "Right answer,\ndifferent format",
            "ambiguous": "Ambiguous question", "gold_wrong": "Broken answer key"}
plt.rcParams.update({"font.family": "DejaVu Sans", "axes.edgecolor": GRID,
                     "axes.spines.top": False, "axes.spines.right": False})


def fig_():
    return plt.figure(figsize=(19.2, 10.8), dpi=100, facecolor="white")


def head(fig, t, sub):
    fig.text(0.04, 0.925, t, fontsize=42, weight="bold", color=INK)
    fig.text(0.04, 0.88, sub, fontsize=19, color=MUTED)


def foot(fig, t):
    fig.text(0.04, 0.02, t, fontsize=14, color=MUTED, va="bottom", linespacing=1.4)


def save(fig, name, folder=HERE):
    p = os.path.join(folder, name + ".png")
    fig.savefig(p, dpi=100, facecolor="white")
    plt.close(fig)
    return p


def is_tune(label):
    return "SFT" in label


def draw_ladder(ax, L, upto=None, examples=False, frontier=True, ymax=100, big=True):
    allsteps = L["steps"]
    steps = allsteps if upto is None else allsteps[:upto + 1]
    n = len(allsteps) + 1  # plus the total bar
    fs = 27 if big else 21
    prev = None
    for i, s in enumerate(steps):
        if s["kind"] == "start":
            ax.bar(i, s["acc"], 0.64, color=START_C)
            ax.text(i, s["acc"] + 1.2, f"{s['acc']:.1f}%", ha="center", va="bottom", fontsize=fs, weight="bold", color=INK)
        else:
            dark, light = (TUNE, TUNE_L) if is_tune(s["label"]) else (HARN, HARN_L)
            ax.bar(i, prev, 0.64, color=light)
            ax.bar(i, max(s["diff"], 0.35), 0.64, bottom=prev, color=dark)
            ax.plot([i - 1 + 0.32, i - 0.32], [prev, prev], color=MUTED, lw=1.4, ls=":")
            ax.text(i, s["acc"] + 4.4, f"+{s['diff']:.1f}", ha="center", va="bottom", fontsize=fs, weight="bold", color=dark)
            sig = "significant" if s["significant"] else "not significant"
            ax.text(i, s["acc"] + 1.0, sig, ha="center", va="bottom", fontsize=12 if not big else 13,
                    color=dark if s["significant"] else MUTED, weight="bold" if s["significant"] else "normal",
                    bbox=dict(facecolor="white", edgecolor="none", pad=1.5), zorder=5)
            if examples:
                kind, ex = CATCH[s["label"]]
                ax.text(i, -0.17, kind, ha="center", va="top", fontsize=15, weight="bold", color=dark,
                        transform=ax.get_xaxis_transform())
                ax.text(i, -0.235, ex, ha="center", va="top", fontsize=13, color=MUTED,
                        transform=ax.get_xaxis_transform(), linespacing=1.3)
        prev = s["acc"]
    if upto is None:
        t = len(allsteps)
        ax.bar(t, L["final_acc"], 0.64, color="white", edgecolor=TOTAL, lw=3.5)
        ax.text(t, L["final_acc"] + 1.2, f"{L['final_acc']:.1f}%", ha="center", va="bottom", fontsize=fs + 5,
                weight="bold", color=TOTAL)
    if frontier:
        ax.axhline(FR["acc"], color="#8e8e93", ls="--", lw=2.4, zorder=0)
        ax.text(-0.45, FR["acc"] + 13, f"- - Claude Sonnet 4.6: {FR['acc']:.1f}%\n    (published, other subset)",
                ha="left", va="bottom", fontsize=15, color=MUTED, linespacing=1.25)
    ax.set_xlim(-0.55, n - 0.45)
    ax.set_xticks(range(n))
    ax.set_xticklabels([SHORT[s["label"]] for s in allsteps] + ["Our\nsystem"], fontsize=17 if big else 14, color=INK)
    ax.set_ylim(0, ymax)
    ax.set_yticks(range(0, ymax + 1, 20))
    ax.set_yticklabels([f"{v}%" for v in range(0, ymax + 1, 20)], fontsize=15, color=MUTED)
    ax.grid(axis="y", color=GRID)
    ax.set_axisbelow(True)
    ax.tick_params(length=0)
    hs = [i for i, s in enumerate(allsteps) if s["kind"] == "step" and not is_tune(s["label"])]
    ts = [i for i, s in enumerate(allsteps) if is_tune(s["label"])]
    for idx, name, col in ((hs, "HARNESS", HARN), (ts, "FINE-TUNING, inside the harness", TUNE)):
        y = ymax - 4
        ax.plot([idx[0] - 0.3, idx[-1] + 0.3], [y, y], color=col, lw=3)
        ax.text((idx[0] + idx[-1]) / 2, y + 0.8, name, ha="center", va="bottom", fontsize=14 if not big else 15,
                weight="bold", color=col)


def SUB(L):
    return (f"Execution accuracy, {L['n']} locked test questions on 5 live Neo4j graphs. "
            "Each step vs the one before, same questions.")


NOTE = ("Significance: paired bootstrap 95% CI vs the previous step. Claude Sonnet 4.6 is a published zero-shot "
        "number on a different subset,\nso it is a reference line, not a step.")


def v1():
    L = LAD["all200"]
    fig = fig_()
    head(fig, f"From {L['steps'][0]['acc']:.1f}% to {L['final_acc']:.1f}%: what each step adds", SUB(L))
    ax = fig.add_axes([0.05, 0.15, 0.92, 0.66])
    draw_ladder(ax, L)
    foot(fig, NOTE)
    return save(fig, "v1_ladder")


def v2():
    L = LAD["all200"]
    fig = fig_()
    head(fig, "What each step catches", SUB(L))
    ax = fig.add_axes([0.05, 0.33, 0.92, 0.49])
    draw_ladder(ax, L, examples=True)
    foot(fig, "Examples are real questions each step newly got right in the run. "
              "Significance: paired bootstrap 95% CI vs the previous step.")
    return save(fig, "v2_ladder_what_it_catches")


def v3(frames=True):
    L = LAD["all200"]
    r = L["miss_reasons"]

    def draw(upto, ceiling):
        fig = fig_()
        title = (f"Why {L['final_acc']:.1f}%, not 100%: mostly the exam" if ceiling
                 else "Building past the frontier, one step at a time")
        head(fig, title, SUB(L))
        ax = fig.add_axes([0.05, 0.15, 0.66, 0.66])
        draw_ladder(ax, L, upto=upto, big=False)
        if ceiling:
            axc = fig.add_axes([0.76, 0.15, 0.06, 0.66])
            axc.bar(0, L["final_acc"], 0.9, color=TOTAL)
            axc.text(0, L["final_acc"] / 2, f"{L['final_acc']:.1f}%\nright", ha="center", va="center",
                     color="white", fontsize=18, weight="bold")
            b = L["final_acc"]
            for k in ("model_wrong", "format_only", "ambiguous", "gold_wrong"):
                h = 100 * r[k] / L["n"]
                axc.bar(0, h, 0.9, bottom=b, color=REASON_C[k])
                fig.text(0.83, 0.15 + 0.66 * (b + h / 2) / 100, f"{REASON_L[k]}  ({r[k]})", va="center",
                         fontsize=16, color=INK, linespacing=1.15)
                b += h
            axc.set_ylim(0, 100)
            axc.axis("off")
            fig.text(0.76, 0.84, f"The {L['misses']} misses", fontsize=22, weight="bold", color=INK)
            exam = r["format_only"] + r["ambiguous"] + r["gold_wrong"]
            fig.text(0.76, 0.12, f"{exam} of {L['misses']} misses are the exam's fault,\nper our audit.",
                     fontsize=15, color=MUTED, va="top", linespacing=1.35)
        foot(fig, NOTE)
        return fig

    paths = []
    if frames:
        fd = os.path.join(HERE, "frames")
        os.makedirs(fd, exist_ok=True)
        k_last = len(L["steps"])
        for k in range(k_last):
            paths.append(save(draw(k, False), f"v3_frame{k + 1:02d}", fd))
        paths.append(save(draw(None, False), f"v3_frame{k_last + 1:02d}", fd))
        paths.append(save(draw(None, True), f"v3_frame{k_last + 2:02d}", fd))
    paths.append(save(draw(None, True), "v3_ladder_why_not_100"))
    return paths


def v4():
    L = LAD["fair175"]
    fig = fig_()
    head(fig, f"On fair questions: {L['steps'][0]['acc']:.1f}% to {L['final_acc']:.1f}%",
         f"{L['n']} questions: the 200, minus {200 - L['n']} our audit found broken or ambiguous. "
         "Each step measured against the one before.")
    ax = fig.add_axes([0.05, 0.15, 0.62, 0.66])
    draw_ladder(ax, L, frontier=False, big=False)
    fig.patches.append(Rectangle((0.70, 0.12), 0.28, 0.72, transform=fig.transFigure, facecolor="#f5f5f7",
                                 edgecolor="none", zorder=-1))
    fig.text(0.72, 0.79, "Tried, did not help", fontsize=26, weight="bold", color=INK)
    y = 0.71
    for t in L["tried"]:
        sig = "significant" if t["significant"] else "not significant"
        col = "#d9534f" if t["diff"] < 0 and t["significant"] else MUTED
        fig.text(0.72, y, t["label"].replace(" instead of SFT", "\ninstead of SFT"), fontsize=17, color=INK,
                 va="top", linespacing=1.2)
        fig.text(0.965, y, f"{t['diff']:+.1f}", fontsize=24, weight="bold", color=col, va="top", ha="right")
        fig.text(0.965, y - 0.045, sig, fontsize=13, color=col, va="top", ha="right")
        y -= 0.13
    fig.text(0.72, 0.17, "Each compared with the setup\nit would have replaced.", fontsize=14, color=MUTED,
             va="top", linespacing=1.35)
    foot(fig, "Frontier reference omitted: the published Claude number is not on this subset. "
              "Significance: paired bootstrap 95% CI.")
    return save(fig, "v4_fair_questions_and_dead_ends")


if __name__ == "__main__":
    for p in [v1(), v2()] + v3() + [v4()]:
        print("wrote", os.path.relpath(p, HERE))
