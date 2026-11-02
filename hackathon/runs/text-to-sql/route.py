#!/usr/bin/env python3
"""Routing simulation from two existing result files: a small model answers; escalate to the large model when the
small answer is invalid, returns an empty result, or has mean token logprob below a threshold. No new API calls:
the escalated rows take the large model's recorded answer, latency and cost, so this is exact for temperature 0.

    python3 route.py results/small.json results/large.json --thresholds -0.5 -0.3 -0.2 -0.1
"""
import argparse, json, os, sqlite3, statistics, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from run_eval import PRICING, DB_ROOT
from score import execute_sql

def empty_result(row):
    if row["invalid"] or not row["pred_sql"]:
        return True
    db = os.path.join(DB_ROOT, row["db_id"], row["db_id"] + ".sqlite")
    r = execute_sql(db, row["pred_sql"])
    return (not r["ok"]) or len(r["rows"]) == 0 or all(all(v is None for v in t) for t in r["rows"])

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("small"); ap.add_argument("large")
    ap.add_argument("--thresholds", nargs="*", type=float, default=[-1.0, -0.5, -0.3, -0.2, -0.1, -0.05])
    ap.add_argument("--no-empty", action="store_true", help="do not escalate on empty result sets")
    ap.add_argument("--out-prefix", default="")
    a = ap.parse_args()
    S, L = json.load(open(a.small)), json.load(open(a.large))
    Ls = {r["id"]: r for r in L["rows"]}
    rows = [r for r in S["rows"] if r["id"] in Ls]
    ps_in, ps_out = PRICING[S["model"]]; pl_in, pl_out = PRICING[L["model"]]
    empties = {r["id"]: (False if a.no_empty else empty_result(r)) for r in rows}
    print(f"small={S['model'].split('/')[-1]}+{S['prompt']} acc {S['accuracy']:.1%} | large={L['model'].split('/')[-1]}+{L['prompt']} acc {L['accuracy']:.1%} | n={len(rows)}")
    print(f"{'threshold':>10s} {'escalated':>9s} {'acc':>6s} {'invalid':>7s} {'p50 s':>6s} {'p95 s':>6s} {'$/1k':>8s}")
    for th in a.thresholds:
        out, cost, lats = [], 0.0, []
        for r in rows:
            lp = r.get("mean_logprob")
            esc = r["invalid"] or empties[r["id"]] or (lp is not None and lp < th)
            cost += (r["in_tokens"] * ps_in + r["out_tokens"] * ps_out) / 1e6
            lat = r["latency"]
            if esc:
                l = Ls[r["id"]]
                cost += (l["in_tokens"] * pl_in + l["out_tokens"] * pl_out) / 1e6
                lat += l["latency"]
                row = dict(l); row["escalated"] = True
            else:
                row = dict(r); row["escalated"] = False
            row["latency"] = lat; lats.append(lat); out.append(row)
        n = len(out); lats.sort()
        summ = {"model": f"route[{S['model'].split('/')[-1]}->{L['model'].split('/')[-1]}]", "prompt": f"{S['prompt']}_th{th}", "mock": False, "n": n,
                "threshold": th, "escalated": sum(r["escalated"] for r in out), "accuracy": round(sum(r["correct"] for r in out) / n, 4),
                "exact_match": round(sum(r["exact"] for r in out) / n, 4), "invalid_outputs": sum(r["invalid"] for r in out),
                "p50_latency_s": round(statistics.median(lats), 3), "p95_latency_s": round(lats[int(0.95 * (n - 1))], 3),
                "cost_total_usd": round(cost, 5), "cost_per_1k_requests_usd": round(cost / n * 1000, 4), "rows": out}
        print(f"{th:10.2f} {summ['escalated']:9d} {summ['accuracy']:6.1%} {summ['invalid_outputs']:7d} {summ['p50_latency_s']:6.2f} {summ['p95_latency_s']:6.2f} {summ['cost_per_1k_requests_usd']:8.4f}")
        if a.out_prefix:
            json.dump(summ, open(f"{a.out_prefix}_th{th}.json", "w"), indent=1)

if __name__ == "__main__":
    main()
