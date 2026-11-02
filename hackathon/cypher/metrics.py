"""Summaries of a run, and "cutting" a full-harness trace at an earlier stage.

Stages run in a fixed order (first -> fix -> repair -> escalate) at temperature 0, so the attempts recorded up to a
stage are exactly what a config that stops at that stage would have produced. One R5 run therefore also gives
R2 (cut at "first"), R3 ("fix") and R4 ("repair"), each with its own cost and latency. HARNESS.md section 8.
"""
import math, statistics
from collections import Counter, defaultdict

STAGES = ["first", "fix", "repair", "escalate"]


def stage_of(source):
    """'first' -> first, 'fix' -> fix, 'repair2' -> repair, anything 'escalate:...' -> escalate."""
    if source.startswith("escalate:"):
        return "escalate"
    return "repair" if source.startswith("repair") else source


def cut(row, upto):
    """The question's result if the harness had stopped after stage `upto`."""
    keep = [a for a in row["attempts"] if STAGES.index(stage_of(a["source"])) <= STAGES.index(upto)]
    if not keep:
        return {"outcome": row.get("outcome", "error"), "stage": "none", "cost": 0.0, "secs": 0.0, "calls": 0}
    # the harness returns the last clean query with rows; failing that, the last one with rows but warnings
    clean = [a for a in keep if a["status"] == "rows"]
    warned = [a for a in keep if a["status"] == "warn"]
    final = (clean or warned or keep)[-1]
    return {"outcome": final["outcome"], "stage": stage_of(final["source"]), "cypher": final["cypher"],
            "cost": sum(a["cost"] for a in keep), "secs": sum(a["secs"] for a in keep),
            "calls": sum(a["calls"] for a in keep)}


def without_warn(row):
    """A --warn run read as if --warn were off. Both configs behave identically until the first query that returns
    rows (clean or warned); without --warn the harness stops there. So truncate there and call warned rows 'rows'."""
    out = []
    for a in row["attempts"]:
        out.append({**a, "status": "rows"} if a["status"] == "warn" else a)
        if a["status"] in ("rows", "warn"):
            break
    return {**row, "attempts": out}


def wilson(k, n, z=1.96):
    """95% confidence interval for a proportion; well-behaved at small n."""
    if n == 0:
        return (0.0, 0.0)
    p = k / n
    centre = (p + z * z / (2 * n)) / (1 + z * z / n)
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / (1 + z * z / n)
    return (round(centre - half, 4), round(centre + half, 4))


def summarize(rows, upto):
    results = [(r, cut(r, upto)) for r in rows]
    n = len(results)
    correct = sum(c["outcome"] == "correct" for _, c in results)

    def acc_by(key):
        groups = defaultdict(list)
        for r, c in results:
            groups[key(r)].append(c["outcome"] == "correct")
        return {g: round(sum(v) / len(v), 4) for g, v in sorted(groups.items())}

    cost = sum(c["cost"] for _, c in results)
    secs = sorted(c["secs"] for _, c in results)
    # where correct answers came from; everything not correct is "wrong"
    sources = Counter(c["stage"] if c["outcome"] == "correct" else "wrong" for _, c in results)
    return {
        "n": n, "correct": correct, "accuracy": round(correct / n, 4) if n else 0.0, "ci95": wilson(correct, n),
        "outcomes": dict(Counter(c["outcome"] for _, c in results)),
        "by_stage": {s: sources.get(s, 0) for s in STAGES + ["wrong"]},
        "by_graph": acc_by(lambda r: r["graph"]), "by_tier": acc_by(lambda r: r["tier"]),
        "cost": round(cost, 6), "cost_per_question": round(cost / n, 6) if n else 0.0,
        "cost_per_correct": round(cost / correct, 6) if correct else None,
        "calls_per_question": round(sum(c["calls"] for _, c in results) / n, 3) if n else 0.0,
        "p50_secs": round(statistics.median(secs), 3) if secs else 0.0,
        "p90_secs": round(secs[min(len(secs) - 1, int(0.9 * len(secs)))], 3) if secs else 0.0,
    }
