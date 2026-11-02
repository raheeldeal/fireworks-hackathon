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


def calibration():
    out = ["# Calibration: does vote agreement predict correctness?", ""]
    for name in ("vote3", "route_big"):
        d = load(name)
        if not d:
            continue
        rows = d["rows"]
        out += [f"## From `{name}` ({len(rows)} rows, three glm-5p3-flash repair chains at T=0.7)", "",
                "| agreement | rows | share | accuracy of voted answer |", "|---|---|---|---|"]
        for a, lab in ((3, "3/3"), (2, "2/3"), (1, "none")):
            rs = [r for r in rows if r["agreement"] == a]
            if name == "route_big" and a == 1:
                # score the small-model fallback (first chain with rows), not the big model's answer
                acc = sum(next((s for s in r["attempt_scores"][:3] if s in ("correct", "wrong")), r["attempt_scores"][0]) == "correct" for r in rs)
            else:
                acc = sum(r["correct"] for r in rs)
            out.append(f"| {lab} | {len(rs)} | {pct(len(rs) / len(rows))} | {pct(acc / len(rs)) if rs else '-'} |")
        if name == "route_big":
            esc = [r for r in rows if r["escalated"]]
            if esc:
                big = sum(r["correct"] for r in esc)
                small = sum(next((s for s in r["attempt_scores"][:3] if s in ("correct", "wrong")), r["attempt_scores"][0]) == "correct" for r in esc)
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
