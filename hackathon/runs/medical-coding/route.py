#!/usr/bin/env python3
"""Routing: a small model answers; escalate to a large model when the small answer is invalid
or its self-reported confidence is below a threshold. Combines two existing results files
(same test set, same seed) so no new API calls are needed. Sweeps thresholds.

  python3 route.py results/glm-5p3-flash_v5_confidence_s7.json results/glm-5p3_v2_rubric_s7.json --thresholds 0.5 0.7 0.8 0.9
"""
import argparse, json, os, statistics
HERE = os.path.dirname(os.path.abspath(__file__))


def combine(small, large, thr):
    big = {r["id"]: r for r in large["rows"]}
    rows = []
    for s in small["rows"]:
        conf = s.get("confidence", 1.0 if not s["invalid"] else 0.0)
        escalate = s["invalid"] or conf < thr
        src = big[s["id"]] if escalate and s["id"] in big else s
        r = dict(src)
        r["escalated"] = bool(escalate and s["id"] in big)
        if r["escalated"]:  # pay for both calls, wait for both (sequential)
            r["cost"] = s["cost"] + src["cost"]
            r["latency"] = s["latency"] + src["latency"]
        rows.append(r)
    n = len(rows)
    lat = sorted(r["latency"] for r in rows)
    cost = sum(r["cost"] for r in rows)
    return {
        "model": f"route({small['model'].split('/')[-1]}->{large['model'].split('/')[-1]})",
        "prompt": f"thr{thr}", "mock": False, "n": n, "seed": small.get("seed"),
        "accuracy": round(sum(r["f1"] for r in rows) / n, 4),
        "exact_accuracy": round(sum(r["correct"] for r in rows) / n, 4),
        "invalid_outputs": sum(r["invalid"] for r in rows),
        "escalation_rate": round(sum(r["escalated"] for r in rows) / n, 4),
        "p50_latency_s": round(statistics.median(lat), 3),
        "p95_latency_s": round(lat[int(0.95 * (n - 1))], 3),
        "cost_per_1k_requests_usd": round(cost / n * 1000, 4),
        "total_cost_usd": round(cost, 4),
        "rows": rows,
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("small")
    ap.add_argument("large")
    ap.add_argument("--thresholds", nargs="+", type=float, default=[0.5, 0.7, 0.8, 0.9])
    args = ap.parse_args()
    small, large = json.load(open(args.small)), json.load(open(args.large))
    for thr in args.thresholds:
        out = combine(small, large, thr)
        p = os.path.join(HERE, "results", f"route_{small['model'].split('/')[-1]}_to_{large['model'].split('/')[-1]}_thr{thr}_s{small.get('seed')}.json")
        json.dump(out, open(p, "w"), indent=2)
        print(f"thr={thr}: F1 {out['accuracy']:.3f} exact {out['exact_accuracy']:.3f} escalated {out['escalation_rate']:.1%} p50 {out['p50_latency_s']}s ${out['cost_per_1k_requests_usd']:.3f}/1k -> {os.path.basename(p)}")


if __name__ == "__main__":
    main()
