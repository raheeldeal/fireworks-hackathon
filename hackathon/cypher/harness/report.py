#!/usr/bin/env python3
"""Build HARNESS_TABLE.md (results table, per-tier) and CALIBRATION.md from results/harness_*.json."""
import glob, json, os, statistics

HERE = os.path.dirname(os.path.abspath(__file__))
RES = os.path.join(os.path.dirname(HERE), "results")
ORDER = ["validate_only", "repair1", "vote3", "route_big", "prune_repair1", "repair1_fewshot", "route_big_u", "repair1_rdefault", "vote3_rdefault", "route_big_u_rdefault", "route_kimi"]


def load(name):
    p = os.path.join(RES, f"harness_{name}.json")
    return json.load(open(p)) if os.path.exists(p) else None


def pct(x):
    return f"{x * 100:.1f}%"


def table():
    lines = ["| config | n | accuracy | lenient | error/invalid | empty | p50 s | p95 s | $/1k | calls/row | escalation |",
             "|---|---|---|---|---|---|---|---|---|---|---|"]
    base = json.load(open(os.path.join(RES, "glm-5p3-flash_v1_plain_n200.json")))
    lines.append(f"| baseline glm-5p3-flash (default reasoning, BASELINES.md run) | {base['n']} | {pct(base['accuracy'])} | {pct(base['accuracy_lenient'])} | "
                 f"{pct(base['error_rate'])} | {pct(base['empty_rate'])} | {base['p50_latency_s']} | {base['p95_latency_s']} | ${base['cost_per_1k_requests_usd']:.3f} | 1 | - |")
    tiers = {}
    for name in ORDER:
        d = load(name)
        if not d:
            continue
        if name == "validate_only":
            n = d["n"]
            plain_err = sum(r["ungated_status"] == "error" for r in d["rows"]) / n
            plain_empty = sum(r["ungated_status"] == "empty" for r in d["rows"]) / n
            lines.append(f"| plain (same run, reasoning low, no gate) | {n} | {pct(d['accuracy_ungated'])} | - | {pct(plain_err)} | {pct(plain_empty)} | "
                         f"{d['p50_latency_s']} | {d['p95_latency_s']} | ${d['cost_per_1k_requests_usd']:.3f} | 1 | - |")
            tiers["plain (low)"] = {t: sum(r["ungated_status"] == "correct" for r in d["rows"] if r["tier"] == t) / max(1, sum(r["tier"] == t for r in d["rows"])) for t in ("easy", "medium", "hard")}
        esc = pct(d["escalation_rate"]) if d["config_detail"]["mode"] == "route" else "-"
        lines.append(f"| {name} | {d['n']} | {pct(d['accuracy'])} | {pct(d['accuracy_lenient'])} | {pct(d['error_rate'])} | {pct(d['empty_rate'])} | "
                     f"{d['p50_latency_s']} | {d['p95_latency_s']} | ${d['cost_per_1k_requests_usd']:.3f} | {d['calls_per_row']} | {esc} |")
        tiers[name] = {t: v["accuracy"] for t, v in d["by_tier"].items()}
    tl = ["| config | easy | medium | hard |", "|---|---|---|---|"]
    for k, v in tiers.items():
        tl.append(f"| {k} | " + " | ".join(pct(v.get(t, 0)) for t in ("easy", "medium", "hard")) + " |")
    return "\n".join(lines), "\n".join(tl)


def r_esc(name, a):
    return True


def small_correct(r):
    """Was the small-model vote right? Agreeing chains return the same rows, so they share a score:
    with agreement 2 or 3 the vote is right iff at least two chains scored correct; with none it is the
    first chain that returned rows."""
    sc = r["attempt_scores"][:3]
    if r["agreement"] in (2, 3):
        return sc.count("correct") >= 2
    return next((s for s in sc if s in ("correct", "wrong")), sc[0]) == "correct"


def calibration():
    out = ["# Calibration: does vote agreement predict correctness?", "",
           "Each row: three glm-5p3-flash generate-and-repair chains at temperature 0.7. Agreement = how many chains returned the same result set (score.py multiset rule). "
           "Accuracy is for the small model's own voted answer, before any escalation. Source: every vote3 / route run in `results/harness_*.json`.", ""]
    names = sorted(os.path.basename(p)[8:-5] for p in glob.glob(os.path.join(RES, "harness_*.json"))
                   if os.path.basename(p)[8:].startswith(("vote3", "route_")))
    pool = {3: [0, 0], 2: [0, 0], 1: [0, 0]}
    esc_pool = {}
    for name in names:
        d = load(name)
        if d["n"] < 200:
            continue
        for r in d["rows"]:
            pool[r["agreement"]][0] += 1; pool[r["agreement"]][1] += small_correct(r)
            if r["escalated"]:
                e = esc_pool.setdefault(r["agreement"], [0, 0, 0]); e[0] += 1; e[1] += small_correct(r); e[2] += r["correct"]
    tot = sum(v[0] for v in pool.values())
    out += [f"## Pooled over {len([n for n in names if load(n)['n'] >= 200])} runs ({tot} row-runs)", "",
            "| agreement | row-runs | share | small-model accuracy |", "|---|---|---|---|"]
    for a, lab in ((3, "3/3"), (2, "2/3"), (1, "none")):
        n_, c_ = pool[a]
        out.append(f"| {lab} | {n_} | {pct(n_ / tot)} | {pct(c_ / n_) if n_ else '-'} |")
    out += ["", "When escalated, glm-5p3 (default reasoning, generate-and-repair) versus the small model's own answer on the same rows:", "",
            "| agreement when escalated | row-runs | small-model accuracy | glm-5p3 accuracy |", "|---|---|---|---|"]
    for a, lab in ((2, "2/3"), (1, "none")):
        if a in esc_pool:
            n_, s_, b_ = esc_pool[a]
            out.append(f"| {lab} | {n_} | {pct(s_ / n_)} | {pct(b_ / n_)} |")
    out += ["", "## Per run", ""]
    for name in names:
        d = load(name)
        if not d:
            continue
        rows = d["rows"]
        out += [f"## From `{name}` ({len(rows)} rows, three glm-5p3-flash repair chains at T=0.7, reasoning {d['reasoning_effort']})", "",
                "| agreement | rows | share | accuracy of small-model voted answer |", "|---|---|---|---|"]
        for a, lab in ((3, "3/3"), (2, "2/3"), (1, "none")):
            rs = [r for r in rows if r["agreement"] == a]
            if name.startswith("route") and r_esc(name, a):
                # score the small-model fallback (first chain with rows), not the big model's answer
                acc = sum(small_correct(r) for r in rs)
            else:
                acc = sum(r["correct"] for r in rs)
            out.append(f"| {lab} | {len(rs)} | {pct(len(rs) / len(rows))} | {pct(acc / len(rs)) if rs else '-'} |")
        if name.startswith("route"):
            esc = [r for r in rows if r["escalated"]]
            if esc:
                big = sum(r["correct"] for r in esc)
                small = sum(small_correct(r) for r in esc)
                out += ["", f"On the {len(esc)} escalated rows: small-model fallback answer {pct(small / len(esc))} correct, glm-5p3 answer {pct(big / len(esc))} correct."]
        out.append("")
    return "\n".join(out)


def prune_savings():
    a, b = load("repair1"), load("prune_repair1")
    if not (a and b):
        return None
    ids = {r["id"]: r for r in a["rows"]}
    pairs = [(ids[r["id"]]["first_in_tokens"], r["first_in_tokens"]) for r in b["rows"] if r["id"] in ids]
    full, pr = sum(p[0] for p in pairs), sum(p[1] for p in pairs)
    pruned_rows = sum(r["pruned"] for r in b["rows"])
    return f"First-call prompt tokens: {full} full vs {pr} pruned ({pct(1 - pr / full)} saved over {len(pairs)} rows; {pruned_rows} rows pruned, the rest fell back to the full schema)."


if __name__ == "__main__":
    t, tiers = table()
    s = prune_savings()
    open(os.path.join(HERE, "HARNESS_TABLE.md"), "w").write(t + "\n\n" + tiers + "\n\n" + (s or "") + "\n")
    open(os.path.join(HERE, "CALIBRATION.md"), "w").write(calibration())
    print(t); print(); print(tiers); print(s); print(); print(calibration())
