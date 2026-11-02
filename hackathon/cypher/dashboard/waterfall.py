"""Waterfall: how each component moves accuracy from the open model to our best system.

  python dashboard/waterfall.py           # run from hackathon/cypher/; writes dashboard/waterfall.png
  python dashboard/waterfall.py --valid   # on the 175 audited-fair questions -> waterfall_valid.png

Each step is one result file read at one stage, compared with the previous step on the same questions (paired
bootstrap 95% CI, compare.py). Steps that were tested but not adopted (they did not beat the step before) are drawn
hollow and do not move the running total. The frontier is a published number on another subset, so it is a reference
line, not a step (it is omitted with --valid, where it would not be comparable).
"""
import json, os, sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
from matplotlib.patches import Patch

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)
import metrics  # noqa: E402
from compare import compare  # noqa: E402

VALID_ONLY = "--valid" in sys.argv
AUDIT = {r["id"]: r["label"] for r in (json.loads(l) for l in open(os.path.join(ROOT, "data", "test_audit.jsonl")))}

START = ("Open model: Muse Glimmer 30B dense, untuned", "r1_base", "first")
# (label, file, stage, adopted, compare_with). An adopted step becomes the new running total. A non-adopted step is an
# alternative, compared with the step it would have replaced (compare_with = that step's file and stage).
STEPS = [
    ("Harness component 1: + 3 retrieved examples", "r5_full", "first", True, None),
    ("Harness component 2: + arrow-direction fix", "r5_full", "fix", True, None),
    ("Harness component 3: + repair loop (database errors)", "r5_full", "repair", True, None),
    ("Harness component 4: + escalation to Kimi K3", "r5_full", "escalate", True, None),
    ("SFT: LoRA on 1.5k verified gold", "r6_ft1", "escalate", True, None),
    ("SFT data: + 9 other graphs (6.5k gold)", "r6bx_ftbx", "escalate", True, None),
    ("RFT-style: own verified answers instead of gold", "r7_ftd", "escalate", False, ("r6_ft1", "escalate")),
    ("Teacher distillation: + Kimi K3 answers", "r6kd_ftkd", "escalate", False, ("r6_ft1", "escalate")),
    ("Hard examples: trace-flagged failures x2", "r6hf_fthf", "escalate", False, ("r6_ft1", "escalate")),
    ("Voting: 4 adapters chosen on dev", "r20_vote_devpick", "first", False, None),
]
FRONTIER = 56.63  # claude-sonnet-4.6 zero-shot, CypherGuard (arxiv.org/html/2610.41755)

INK, INK2, MUTED, GRID = "#0b0b0b", "#52514e", "#898781", "#e1e0d9"
NOTE_GAP = 4  # the delta-label column starts this far right of the longest bar (and the frontier line)
CLEAR = dict(facecolor="white", edgecolor="none", pad=1.5)
UP, HOLD, TOTAL = "#2a78d6", "#c3c2b7", "#52514e"


def correct_by_id(tag, stage):
    doc = json.load(open(os.path.join(ROOT, "results", f"{tag}.json")))
    return {r["id"]: metrics.cut(r, stage)["outcome"] == "correct" for r in doc["rows"]
            if not VALID_ONLY or AUDIT.get(r["id"]) not in ("gold_wrong", "ambiguous")}


def main():
    current = correct_by_id(*START[1:])
    start_acc = 100 * sum(current.values()) / len(current)
    chain = [(START[0], 0, start_acc, "total", "")]  # the waterfall itself: start, adopted steps, overall
    tried = []                                        # alternatives that were tested and not adopted
    level = start_acc
    for label, tag, stage, adopted, compare_with in STEPS:
        if not os.path.exists(os.path.join(ROOT, "results", f"{tag}.json")):
            continue
        new = correct_by_id(tag, stage)
        ref = correct_by_id(*compare_with) if compare_with else current
        r = compare(ref, new)
        diff, (lo, hi) = 100 * r["diff"], r["ci95"]
        sig = "significant" if lo > 0 or hi < 0 else "n.s."
        note = f"{diff:+.1f}pp  [{100 * lo:+.1f}, {100 * hi:+.1f}]  {sig}"
        if adopted:
            chain.append((label, level, level + diff, "up", note))
            level += diff
            current = new
        else:  # drawn from the level of the step it is compared with
            ref_level = 100 * sum(ref.values()) / len(ref)
            tried.append((label, ref_level, ref_level + diff, "hold", note))
    chain.append(("Overall: best system", 0, level, "total", ""))

    # frontier baselines, drawn as reference bars above the chain (they are not steps)
    refs = ([("Frontier baseline: Claude Sonnet 4.6, zero-shot (published, other subset)", FRONTIER)] if not VALID_ONLY else [])
    if os.path.exists(os.path.join(ROOT, "results", "r23_kimi_plain.json")):  # zero-shot: no examples, no harness
        kimi = correct_by_id("r23_kimi_plain", "first")
        refs.append(("Frontier proxy, run by us: Kimi K3 (2.8T MoE), zero-shot, no harness", 100 * sum(kimi.values()) / len(kimi)))

    # rows top to bottom: references, gap, chain, gap, tested-but-not-adopted block
    n_rows = len(refs) + 1 + len(chain) + (1 + len(tried) if tried else 0)
    fig, ax = plt.subplots(figsize=(14, 0.62 * n_rows + 2.2), dpi=150)
    top = n_rows - 1
    ref_y = [top - k for k in range(len(refs))]
    chain_y = [top - len(refs) - 1 - k for k in range(len(chain))]
    tried_y = [chain_y[-1] - 2 - k for k in range(len(tried))]

    for y, (label, v) in zip(ref_y, refs):
        ax.barh(y, v, height=0.6, color="white", edgecolor=INK2, hatch="//", linewidth=1, zorder=3)
        ax.text(v + 0.8, y, f"{v:.1f}%", va="center", fontsize=11, color=INK2, fontweight="bold", bbox=CLEAR, zorder=4)
    ax.axhline(top - len(refs), color=GRID, linewidth=1)

    ends = [max(a, b) for _, a, b, _, _ in chain + tried] + [v for _, v in refs]
    NOTE_X = max(ends) + NOTE_GAP  # one aligned column, clear of every bar and the frontier line
    prev_end, prev_y = None, None
    for y, (label, a, b, kind, note) in zip(chain_y, chain):
        lo_, hi_ = min(a, b), max(a, b)
        if kind == "total":
            ax.barh(y, hi_, height=0.6, color=TOTAL, zorder=3)
            ax.text(hi_ + 0.8, y, f"{hi_:.1f}%", va="center", fontsize=11, color=INK, fontweight="bold", bbox=CLEAR, zorder=4)
        elif kind == "frontier":
            ax.barh(y, hi_, height=0.6, color="white", edgecolor=INK2, hatch="//", linewidth=1)
            ax.text(hi_ + 0.8, y, f"{hi_:.1f}%  (reference, not a step)", va="center", fontsize=9.5, color=INK2)
            continue  # not part of the chain: no connectors to or from it
        else:
            ax.barh(y, max(hi_ - lo_, 0.25), left=lo_, height=0.6, color=UP, zorder=3)
            ax.text(NOTE_X, y, note, va="center", fontsize=9.5, color=INK, zorder=4)
        if prev_end is not None:  # connector: previous running total down to this bar
            ax.plot([prev_end, prev_end], [prev_y - 0.3, y + 0.3], color=MUTED, linewidth=1)
        prev_end, prev_y = (hi_ if kind == "total" else b), y

    if tried:
        gap_y = chain_y[-1] - 1
        ax.axhline(gap_y, color=GRID, linewidth=1)
        ax.text(0.5, gap_y, "Tested, not adopted (each vs the step it would replace)", va="center", fontsize=9.5,
                color=MUTED, style="italic", backgroundcolor="white")
        for y, (label, a, b, kind, note) in zip(tried_y, tried):
            lo_, hi_ = min(a, b), max(a, b)
            ax.barh(y, max(hi_ - lo_, 0.25), left=lo_, height=0.6, color="white", edgecolor=MUTED, linewidth=1.2,
                    linestyle=(0, (3, 2)))
            ax.text(NOTE_X, y, note, va="center", fontsize=9.5, color=MUTED, zorder=4)

    labels = ({y: r[0] for y, r in zip(ref_y, refs)} | {y: c[0] for y, c in zip(chain_y, chain)}
              | {y: t[0] for y, t in zip(tried_y, tried)})
    ax.set_yticks(list(labels), list(labels.values()), fontsize=10)
    ax.set_ylim(min(labels) - 0.7, top + 0.7)
    ax.tick_params(colors=MUTED)
    ax.tick_params(axis="y", labelcolor=INK)
    ax.set_xlim(0, NOTE_X + 30)
    ax.set_xticks(range(0, 101, 20))
    ax.set_xlabel("execution accuracy (%)", fontsize=10.5, color=INK)
    ax.xaxis.grid(True, color=GRID)
    ax.set_axisbelow(True)
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)
    scope = "175 audited-fair test questions" if VALID_ONLY else "200 locked test questions, strict execution accuracy"
    ax.set_title(f"From open model to best system: what each component adds\n{scope}\n"
                 f"each step vs the step before it (or the step it replaces), same questions, paired bootstrap 95% CI",
                 loc="left", fontsize=12, color=INK, pad=12)
    ax.legend(handles=[Patch(facecolor=TOTAL, label="start / overall"), Patch(facecolor=UP, label="adopted step"),
                       Patch(facecolor="white", edgecolor=MUTED, linestyle="--", label="tested, not adopted")]
              + [Patch(facecolor="white", edgecolor=INK2, hatch="//", label="frontier baseline (reference, not a step)")],
              loc="upper center", bbox_to_anchor=(0.5, -0.07), ncol=4, fontsize=9, frameon=False)  # below the axis
    fig.tight_layout()
    out = os.path.join(HERE, "waterfall_valid.png" if VALID_ONLY else "waterfall.png")
    fig.savefig(out, facecolor="white", bbox_inches="tight")
    print("wrote", os.path.relpath(out, ROOT), f"start {start_acc:.1f}% -> overall {level:.1f}%")


if __name__ == "__main__":
    main()
