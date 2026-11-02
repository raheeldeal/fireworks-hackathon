#!/usr/bin/env python3
"""Routing: small model answers; escalate to the large model when invalid or low-confidence.
Confidence = number of 'risk' signals in the small model's output/input: invalid JSON, price present with a second $ amount in text,
'available in' colour phrase, pack/set language, bundle words, size range. Threshold t = escalate when risk >= t.
Uses existing result files (no new calls for the small model); large-model answers come from its result file, so all rows must be present.
Usage: python3 route.py results/small.json results/large.json --thresholds 1 2 3 --out results/route_
"""
import argparse, json, os, re, statistics, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import fw

def risk(row):
    t = row["text"].lower(); r = 0
    if not row["valid"]: r += 10
    if len(re.findall(r"\$\s?\d", row["text"])) >= 2: r += 1
    if re.search(r"available in|also comes in|other colou?rs", t): r += 1
    if re.search(r"pack of|set of|\d+-pack|\d+ pack|\bpcs\b|count\)", t): r += 1
    if re.search(r"bundle|kit|comes with|includes", t): r += 1
    if re.search(r"sizes? (xs|s|\d+)\s*(-|to|–)", t) or re.search(r"available (in )?(xs|s)-", t): r += 1
    return r

ap = argparse.ArgumentParser(); ap.add_argument("small"); ap.add_argument("large"); ap.add_argument("--thresholds", nargs="+", type=int, default=[1, 2, 3]); ap.add_argument("--out", default="results/route_")
a = ap.parse_args()
S, L = json.load(open(a.small)), json.load(open(a.large))
lrows = {r["id"]: r for r in L["rows"]}
for t in a.thresholds:
    rows, esc = [], 0
    for s in S["rows"]:
        if s["id"] not in lrows: continue
        if risk(s) >= t:
            l = dict(lrows[s["id"]]); l["latency"] = s["latency"] + l["latency"]; l["in_tok"] += s["in_tok"]; l["out_tok"] += s["out_tok"]; l["escalated"] = True; esc += 1
            l["cost"] = fw.cost_of(S["model"], s["in_tok"], s["out_tok"]) + fw.cost_of(L["model"], lrows[s["id"]]["in_tok"], lrows[s["id"]]["out_tok"]); rows.append(l)
        else:
            s = dict(s); s["escalated"] = False; s["cost"] = fw.cost_of(S["model"], s["in_tok"], s["out_tok"]); rows.append(s)
    n = len(rows); lat = sorted(r["latency"] for r in rows); cost = sum(r["cost"] for r in rows)
    summ = {"model": f"{S['model'].split('/')[-1]}->{L['model'].split('/')[-1]}", "prompt": f"route_t{t}", "json_mode": S.get("json_mode"), "seed": S.get("seed"), "mock": False, "n": n,
            "accuracy": round(sum(r["correct"] for r in rows) / n, 4), "mean_field_accuracy": round(sum(r["n_correct"] for r in rows) / (8 * n), 4),
            "invalid_outputs": sum(not r["valid"] for r in rows), "escalated": esc, "escalation_rate": round(esc / n, 3),
            "p50_latency_s": round(statistics.median(lat), 3), "p95_latency_s": round(lat[int(0.95 * (n - 1))], 3), "cost_usd": round(cost, 4),
            "cost_per_1k_requests_usd": round(cost / n * 1000, 4), "rows": rows}
    out = f"{a.out}t{t}.json"; json.dump(summ, open(out, "w"), indent=1)
    print(f"t={t}: escalated {esc}/{n} ({esc/n:.0%}) acc {summ['accuracy']:.1%} invalid {summ['invalid_outputs']} p50 {summ['p50_latency_s']}s ${summ['cost_per_1k_requests_usd']:.3f}/1k -> {out}")
