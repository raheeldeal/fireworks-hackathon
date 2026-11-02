#!/usr/bin/env python3
"""Offline routing sweep: small model answers; escalate to the big model when the small answer is invalid or its
confidence (mean answer-token logprob) is below a threshold. Both results files must cover the same test rows.

  python3 route.py results/<small>.json results/<big>.json [--thresholds -0.5,-0.2,-0.1,-0.05,-0.02]
Writes results/route_<small>_to_<big>.json (one summary per threshold, same shape as run_eval output, no rows).
"""
import argparse, json, os, statistics
HERE = os.path.dirname(os.path.abspath(__file__))

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("small"); ap.add_argument("big")
    ap.add_argument("--thresholds", default="-1.0,-0.5,-0.3,-0.2,-0.1,-0.05,-0.02,-0.01")
    args = ap.parse_args()
    S, B = json.load(open(args.small)), json.load(open(args.big))
    big = {r["id"]: r for r in B["rows"]}
    small = [r for r in S["rows"] if r["id"] in big]
    n = len(small)
    ps = {"small": (S["in_tokens"] * 0 + S["total_cost_usd"]) / S["n"], "big": B["total_cost_usd"] / B["n"]}  # $ per row
    out = []
    confs = [r["confidence"] for r in small if r["confidence"] is not None]
    print(f"{n} shared rows; small conf: min {min(confs):.3f} median {statistics.median(confs):.3f} max {max(confs):.3f}" if confs else "no confidence values")
    print(f"{'threshold':>10s} {'escalated':>9s} {'acc':>6s} {'partial':>7s} {'$/1k':>7s} {'p50 s':>6s} {'p95 s':>6s}")
    for t in [None] + [float(x) for x in args.thresholds.split(",")]:
        strict = partial = cost = 0.0; esc = 0; lats = []
        for r in small:
            c = r["confidence"]
            go_big = r["invalid"] or (t is not None and (c is None or c < t))
            if go_big:
                b = big[r["id"]]; esc += 1
                strict += b["strict"]; partial += b["partial"]; cost += ps["small"] + ps["big"]; lats.append(r["latency"] + b["latency"])
            else:
                strict += r["strict"]; partial += r["partial"]; cost += ps["small"]; lats.append(r["latency"])
        lats.sort()
        row = {"model": f"route:{S['model'].split('/')[-1]}->{B['model'].split('/')[-1]}", "prompt": S["prompt"], "mode": S["mode"],
               "threshold": "invalid-only" if t is None else t, "n": n, "escalated": esc, "escalated_frac": round(esc / n, 3),
               "accuracy": round(strict / n, 4), "accuracy_partial": round(partial / n, 4), "invalid_outputs": 0,
               "p50_latency_s": round(statistics.median(lats), 3), "p95_latency_s": round(lats[int(0.95 * (n - 1))], 3),
               "cost_per_1k_requests_usd": round(cost / n * 1000, 4), "mock": False}
        out.append(row)
        print(f"{row['threshold']!s:>10s} {esc:9d} {row['accuracy']:6.1%} {row['accuracy_partial']:7.1%} {row['cost_per_1k_requests_usd']:7.3f} {row['p50_latency_s']:6.2f} {row['p95_latency_s']:6.2f}")
    print(f"{'small only':>10s} {0:9d} {S['accuracy']:6.1%} {S['accuracy_partial']:7.1%} {S['cost_per_1k_requests_usd']:7.3f}")
    print(f"{'big only':>10s} {n:9d} {B['accuracy']:6.1%} {B['accuracy_partial']:7.1%} {B['cost_per_1k_requests_usd']:7.3f}")
    name = f"route_{os.path.basename(args.small)[:-5]}_to_{os.path.basename(args.big)[:-5]}.json"
    json.dump(out, open(os.path.join(HERE, "results", name), "w"), indent=1)
    print("saved results/" + name)

if __name__ == "__main__":
    main()
