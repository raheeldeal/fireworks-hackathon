"""Why each method helps: head-to-head wins between pairs of configs, split by why the losing side failed.

  python dashboard/why.py      # run from hackathon/cypher/; writes dashboard/why.png

Uses the 175 audited-fair test questions (drops gold_wrong / ambiguous in data/test_audit.jsonl). For each pair, the
left bar counts questions only A answers correctly, the right bar questions only B answers correctly, each split by
the loser's failure type. Failure types are approximate, from the final query's row count and columns vs gold:
  query failed       error, or no rows
  different columns  right number of rows, different number of columns (answer shape / dataset convention)
  wrong values       right shape, wrong values or wrong row set (query logic)
The frontier-proxy model is Kimi K3 (2.8T): no closed frontier model was run.
"""
import collections, json, os, sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Patch

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)
import metrics  # noqa: E402

RUNS = {"Muse 30B dense, untuned": ("r1_base", "first"), "Muse 30B dense, untuned + harness": ("r5_full", "escalate"),
        "Kimi K3 (2.8T MoE) + harness, frontier proxy": ("r17_kimi", "repair"), "Muse 30B dense + SFT (1.5k gold)": ("r6_ft1", "escalate"),
        "Muse 30B dense + SFT (6.5k gold, 14 graphs)": ("r6bx_ftbx", "escalate"), "Muse 30B dense + RFT-style (own verified answers)": ("r7_ftd", "escalate")}
PAIRS = [("Muse 30B dense, untuned", "Muse 30B dense, untuned + harness", "What the harness adds"),
         ("Muse 30B dense, untuned", "Muse 30B dense + SFT (1.5k gold)", "What SFT adds"),
         ("Kimi K3 (2.8T MoE) + harness, frontier proxy", "Muse 30B dense + SFT (6.5k gold, 14 graphs)", "Frontier proxy vs our best fine-tuned model"),
         ("Muse 30B dense + RFT-style (own verified answers)", "Muse 30B dense + SFT (1.5k gold)", "RFT-style (training on its own verified answers) vs SFT on gold")]
KINDS = [("query failed", "#1baf7a"), ("different columns", "#eb6834"), ("wrong values", "#2a78d6")]
INK, MUTED, GRID = "#0b0b0b", "#898781", "#e1e0d9"


def load_runs():
    out = {}
    for name, (tag, stage) in RUNS.items():
        doc = json.load(open(os.path.join(ROOT, "results", f"{tag}.json")))
        out[name] = {r["id"]: (r, metrics.cut(r, stage)) for r in doc["rows"]}
    return out


def failure_kind(row, cut, gold):
    if cut["outcome"] in ("error", "empty"):
        return "query failed"
    a = next((a for a in reversed(row["attempts"]) if a["cypher"] == cut.get("cypher")), None)
    ncols = len(a["preview"][0]) if a and a.get("preview") else 0
    if a and a["n_rows"] == len(gold["rows"]) and ncols != len(gold["columns"]):
        return "different columns"
    return "wrong values"


def main():
    test = {json.loads(l)["id"]: json.loads(l) for l in open(os.path.join(ROOT, "data", "test.jsonl"))}
    audit = {r["id"]: r["label"] for r in (json.loads(l) for l in open(os.path.join(ROOT, "data", "test_audit.jsonl")))}
    fair = [i for i in test if audit.get(i) not in ("gold_wrong", "ambiguous")]
    runs = load_runs()
    ok = lambda name, i: runs[name][i][1]["outcome"] == "correct"

    fig, axes = plt.subplots(len(PAIRS) + 1, 1, figsize=(13, 2.0 * (len(PAIRS) + 1) + 1.4), dpi=150,
                             gridspec_kw={"height_ratios": [1] * len(PAIRS) + [1.25]})
    for ax, (a, b, title) in zip(axes, PAIRS):
        sides = []
        for winner, loser in ((a, b), (b, a)):
            ids = [i for i in fair if ok(winner, i) and not ok(loser, i)]
            kinds = collections.Counter(failure_kind(*runs[loser][i], test[i]["gold_result"]) for i in ids)
            sides.append((winner, loser, len(ids), kinds))
        for y, (winner, loser, n, kinds) in zip((1, 0), sides):
            left = 0
            for kind, color in KINDS:
                v = kinds.get(kind, 0)
                if v:
                    ax.barh(y, v, left=left, height=0.62, color=color, edgecolor="white", linewidth=2)
                    if v >= 3:
                        ax.text(left + v / 2, y, str(v), ha="center", va="center", fontsize=9, color="white")
                    left += v
            ax.text(left + 0.6, y, f"{n} questions only {winner} gets right", va="center", fontsize=9.5, color=INK)
        ax.set_yticks([1, 0], [f"{sides[0][0]} wins", f"{sides[1][0]} wins"], fontsize=9.5, color=INK)
        ax.set_title(title, loc="left", fontsize=11, color=INK, pad=4)
        ax.set_xlim(0, 75)
        ax.xaxis.grid(True, color=GRID)
        ax.set_axisbelow(True)
        for s in ("top", "right"):
            ax.spines[s].set_visible(False)
        ax.tick_params(colors=MUTED)
        ax.tick_params(axis="y", labelcolor=INK)
    axes[len(PAIRS) - 1].set_xlabel("questions (of 175 audited-fair test questions), split by why the other side failed",
                                    fontsize=9.5, color=INK)

    # last panel: accuracy by difficulty tier, frontier proxy vs best SFT
    ax = axes[-1]
    tiers = ["easy", "medium", "hard"]
    names = ["Kimi K3 (2.8T MoE) + harness, frontier proxy", "Muse 30B dense + SFT (6.5k gold, 14 graphs)"]
    colors = ["#c3c2b7", "#2a78d6"]
    for k, (name, color) in enumerate(zip(names, colors)):
        vals, ns = [], []
        for t in tiers:
            ids = [i for i in fair if test[i]["complexity"]["tier"] == t]
            vals.append(100 * sum(ok(name, i) for i in ids) / len(ids))
            ns.append(len(ids))
        xs = [j + (k - 0.5) * 0.36 for j in range(len(tiers))]
        ax.bar(xs, vals, width=0.34, color=color, label=name)
        for x, v in zip(xs, vals):
            ax.text(x, v + 1.5, f"{v:.0f}%", ha="center", fontsize=9.5, color=INK)
    ax.set_xticks(range(len(tiers)), [f"{t} (n={n})" for t, n in zip(tiers, ns)], fontsize=9.5, color=INK)
    ax.set_ylim(0, 112)
    ax.tick_params(axis="x", labelcolor=INK)
    ax.set_ylabel("accuracy (%)", fontsize=9.5, color=INK)
    ax.set_title("By difficulty: the frontier proxy wins on hard multi-step queries, SFT on everyday ones",
                 loc="left", fontsize=11, color=INK, pad=4)
    ax.yaxis.grid(True, color=GRID)
    ax.set_axisbelow(True)
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)
    ax.tick_params(colors=MUTED)
    ax.tick_params(axis="x", labelcolor=INK)  # tier names in primary ink
    ax.legend(frameon=False, fontsize=9, loc="upper left", ncol=2)

    fig.legend(handles=[Patch(facecolor=c, label=f"loser: {k}") for k, c in KINDS], loc="upper left",
               ncol=3, frameon=False, fontsize=9.5, bbox_to_anchor=(0.005, 0.975))
    fig.suptitle("Why each method helps: head-to-head wins on the same questions",
                 x=0.01, ha="left", fontsize=13, color=INK, y=0.995)
    fig.text(0.01, 0.005, "Frontier proxy = Kimi K3 (no closed frontier model run). Failure types approximate (row count "
             "and columns vs gold).", fontsize=8, color=MUTED)
    fig.tight_layout(rect=(0, 0.015, 1, 0.945))
    out = os.path.join(HERE, "why.png")
    fig.savefig(out, facecolor="white", bbox_inches="tight")
    print("wrote", os.path.relpath(out, ROOT))


if __name__ == "__main__":
    main()
