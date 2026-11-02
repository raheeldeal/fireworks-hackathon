"""Before -> after chart: each config's accuracy and its paired change vs the untuned base model (R1).

  python dashboard/before_after.py           # run from hackathon/cypher/; writes dashboard/before_after.png
  python dashboard/before_after.py --valid   # same on the 175 audited-fair questions -> before_after_valid.png

Delta = config minus baseline on the same 200 test questions, with a paired bootstrap 95% CI (compare.py).
"Significant" means that interval excludes zero. Claude Sonnet 4.6 is a published number on a different subset of the
same dataset, so it is drawn as a reference line, not a bar (it cannot be paired with our questions).
Configs chosen on the test set (e.g. R19) are left out.
"""
import json, os, sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Patch

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)
import metrics  # noqa: E402
from compare import compare  # noqa: E402

BASELINE = ("Muse Glimmer 30B dense, no tuning, no harness (baseline)", "r1_base", "first")
CONFIGS = [  # label, result file, stage
    ("Muse 30B dense + SFT (6.5k gold, 14 graphs) + harness", "r6bx_ftbx", "escalate"),
    ("Muse 30B dense + SFT (1.5k gold) + harness", "r6_ft1", "escalate"),
    ("Vote of 4 Muse 30B dense adapters (picked on dev)", "r20_vote_devpick", "first"),
    ("Muse 30B dense + SFT + Kimi K3 teacher answers + harness", "r6kd_ftkd", "escalate"),
    ("Muse 30B dense + SFT, trace-flagged failures x2 + harness", "r6hf_fthf", "escalate"),
    ("Muse 30B dense + SFT (4.4k gold, 1 epoch) + harness", "r6b_ft1big", "escalate"),
    ("Muse 30B dense + SFT (1.5k gold), no examples", "r6z_ft1_noshots", "escalate"),
    ("Kimi K3 (2.8T MoE) + harness", "r17_kimi", "repair"),
    ("GLM 5.3 (743B MoE) + harness", "r15_glm", "repair"),
    ("Muse 30B dense + RFT-style (own verified answers) + harness", "r7_ftd", "escalate"),
    ("Muse 30B dense, untuned + full harness", "r5_full", "escalate"),
    ("gpt-oss-120b (117B MoE, 5.1B active) + harness", "r13_gptoss", "escalate"),
    ("Muse 30B dense, untuned + examples only", "r5_full", "first"),
    ("Qwen2.5 1.5B dense, untuned, local + examples + arrow fix", "r22_qwen15", "fix"),
]
FRONTIER = 0.5663  # claude-sonnet-4.6 zero-shot, CypherGuard (arxiv.org/html/2610.41755)

# validated palette (dataviz reference instance, light mode)
INK, INK2, MUTED, GRID = "#0b0b0b", "#52514e", "#898781", "#e1e0d9"
BETTER, NEUTRAL, WORSE, BASE = "#2a78d6", "#c3c2b7", "#eb6834", "#52514e"


VALID_ONLY = "--valid" in sys.argv  # drop gold_wrong / ambiguous questions (data/test_audit.jsonl)
AUDIT = {r["id"]: r["label"] for r in (json.loads(l) for l in open(os.path.join(ROOT, "data", "test_audit.jsonl")))}


def correct_by_id(tag, stage):
    doc = json.load(open(os.path.join(ROOT, "results", f"{tag}.json")))
    return {r["id"]: metrics.cut(r, stage)["outcome"] == "correct" for r in doc["rows"]
            if not VALID_ONLY or AUDIT.get(r["id"]) not in ("gold_wrong", "ambiguous")}


def main():
    base = correct_by_id(*BASELINE[1:])
    base_acc = sum(base.values()) / len(base)
    rows = []
    for label, tag, stage in CONFIGS:
        if not os.path.exists(os.path.join(ROOT, "results", f"{tag}.json")):
            continue  # still running
        ok = correct_by_id(tag, stage)
        r = compare(base, ok)
        rows.append((label, r["acc_b"], r["diff"], r["ci95"]))
    rows.sort(key=lambda x: x[1], reverse=True)

    labels = [BASELINE[0]] + [r[0] for r in rows]
    accs = [base_acc] + [r[1] for r in rows]
    fig, ax = plt.subplots(figsize=(14, 0.62 * len(labels) + 1.8), dpi=150)
    ys = list(range(len(labels)))[::-1]
    for y, (label, acc) in zip(ys, zip(labels, accs)):
        if label == BASELINE[0]:
            ax.barh(y, 100 * acc, height=0.62, color=BASE, hatch="//", edgecolor=INK, linewidth=0.8)
            continue
        _, _, diff, (lo, hi) = rows[labels.index(label) - 1]
        sig_better, sig_worse = lo > 0, hi < 0
        color = BETTER if sig_better else WORSE if sig_worse else NEUTRAL
        ax.barh(y, 100 * acc, height=0.62, color=color)
        verdict = "significant" if sig_better or sig_worse else "n.s."
        ax.text(101.5, y, f"{100 * diff:+.1f}pp  [{100 * lo:+.1f}, {100 * hi:+.1f}]  {verdict}",
                va="center", fontsize=9.5, color=INK if verdict == "significant" else MUTED)
    for y, acc in zip(ys, accs):
        ax.text(100 * acc + 0.8, y, f"{100 * acc:.1f}%", va="center", fontsize=10, color=INK)

    if not VALID_ONLY:  # the published number was not audited like our subset, so it is only drawn on the full set
        ax.axvline(100 * FRONTIER, color=INK2, linestyle=(0, (4, 3)), linewidth=1.2)
        ax.text(100 * FRONTIER, len(labels) - 0.35, "Claude Sonnet 4.6, 56.6%\n(published, other subset)",
                ha="center", va="bottom", fontsize=9, color=INK2)
    ax.set_yticks(ys, labels, fontsize=10, color=INK)
    ax.set_xlim(0, 100)
    ax.set_ylim(-0.7, len(labels) + 0.4)
    ax.set_xlabel("execution accuracy on the locked text-to-Cypher test set (%)", fontsize=10.5, color=INK)
    ax.xaxis.grid(True, color=GRID, linewidth=1)
    ax.set_axisbelow(True)
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)
    ax.spines["left"].set_color(MUTED)
    ax.spines["bottom"].set_color(MUTED)
    ax.tick_params(colors=MUTED)
    ax.tick_params(axis="y", labelcolor=INK)  # config names in primary ink; ticks and axis stay recessive
    scope = ("175 audited-fair questions (5 wrong-gold and 20 ambiguous removed)" if VALID_ONLY
             else "200 questions, 5 live Neo4j graphs")
    ax.set_title("Before → after: what beats the untuned base model?\n"
                 f"{scope}; Δ vs baseline with paired bootstrap 95% CI on the same questions",
                 loc="left", fontsize=12, color=INK, pad=28)
    used = {"better": any(lo > 0 for *_, (lo, hi) in rows), "neutral": any(lo <= 0 <= hi for *_, (lo, hi) in rows),
            "worse": any(hi < 0 for *_, (lo, hi) in rows)}
    handles = [Patch(facecolor=BASE, hatch="//", edgecolor=INK, label="baseline")]
    handles += [Patch(facecolor=c, label=t) for k, c, t in (("better", BETTER, "significantly better"),
                ("neutral", NEUTRAL, "not significant"), ("worse", WORSE, "significantly worse")) if used[k]]
    ax.legend(handles=handles, loc="lower right", fontsize=9, frameon=False)  # only categories that appear
    fig.text(0.995, 0.005, "Δ text: change in percentage points vs baseline, [95% CI]", ha="right", fontsize=8, color=MUTED)
    fig.tight_layout()
    out = os.path.join(HERE, "before_after_valid.png" if VALID_ONLY else "before_after.png")
    fig.savefig(out, facecolor="white", bbox_inches="tight")
    print(f"wrote {os.path.relpath(out, ROOT)} with {len(rows)} configs vs baseline {base_acc:.1%}")


if __name__ == "__main__":
    main()
