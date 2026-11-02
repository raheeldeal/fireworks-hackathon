#!/usr/bin/env python3
"""Offline routing: small model answers; escalate to the large model when the small answer is invalid
or its confidence (geometric-mean token probability from logprobs) is below a threshold.

    venv/bin/python route.py results/<small>.json results/<large>.json --thresholds 0.5 0.7 0.85 0.95

Writes results/route_<small>_<large>_t<thr>.json in the same shape as run_eval.py output. No API calls:
both result files must already cover the same test rows (the large file may be a subset; rows the large
model never answered are served by the small model and counted as such).
"""
import argparse
import json
import os
import statistics

HERE = os.path.dirname(os.path.abspath(__file__))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("small")
    ap.add_argument("large")
    ap.add_argument("--thresholds", nargs="+", type=float, default=[0.0, 0.5, 0.7, 0.85, 0.95])
    args = ap.parse_args()
    S, L = json.load(open(args.small)), json.load(open(args.large))
    lrows = {r["id"]: r for r in L["rows"]}
    s_cost_row = S["cost_per_1k_requests_usd"] / 1000
    l_cost_row = L["cost_per_1k_requests_usd"] / 1000
    for t in args.thresholds:
        rows, esc, lat = [], 0, []
        for r in S["rows"]:
            conf = r.get("confidence")
            escalate = (not r["valid"]) or (conf is not None and conf < t)
            if escalate and r["id"] in lrows:
                esc += 1
                lr = dict(lrows[r["id"]])
                lr["routed_to"] = "large"
                lr["latency"] = round(r["latency"] + lr["latency"], 3)  # small call happened first
                rows.append(lr)
                lat.append(lr["latency"])
            else:
                rr = dict(r)
                rr["routed_to"] = "small"
                rows.append(rr)
                lat.append(r["latency"])
        n = len(rows)
        frac = esc / n
        cost_per_1k = (s_cost_row + frac * l_cost_row) * 1000
        ls = sorted(lat)
        summary = {
            "model": f"route[{S['model'].split('/')[-1]}->{L['model'].split('/')[-1]}]",
            "prompt": f"{S['prompt']}_thr{t}", "mock": False, "n": n,
            "accuracy": round(sum(r["correct"] for r in rows) / n, 4),
            "soft_score": round(sum(r["soft"] for r in rows) / n, 4),
            "invalid_outputs": sum(not r["valid"] for r in rows),
            "timeouts": sum(r["timeouts"] for r in rows), "truncated": 0,
            "p50_latency_s": round(statistics.median(lat), 3), "p95_latency_s": round(ls[int(0.95 * (n - 1))], 3),
            "cost_per_1k_requests_usd": round(cost_per_1k, 4), "escalated": esc, "escalation_rate": round(frac, 4),
            "threshold": t, "seed": 0, "rows": rows,
        }
        out = os.path.join(HERE, "results", f"route_{S['model'].split('/')[-1]}_{L['model'].split('/')[-1]}_t{t}.json")
        json.dump(summary, open(out, "w"), indent=1, ensure_ascii=False)
        print(f"thr {t:4.2f}: acc {summary['accuracy']:.1%} soft {summary['soft_score']:.3f} escalated {esc:3d} ({frac:.0%}) "
              f"${cost_per_1k:.4f}/1k p50 {summary['p50_latency_s']}s -> {os.path.basename(out)}")


if __name__ == "__main__":
    main()
