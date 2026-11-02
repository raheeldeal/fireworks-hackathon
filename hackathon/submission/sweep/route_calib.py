#!/usr/bin/env python3
"""Offline routing + calibration from per-row result files (no API calls; exact at temperature 0).
Confidence = self-reported `confidence` field when the output is JSON with one (v5_conf runs), else first-token logprob (--logprobs runs).
Escalate when confidence < threshold or the small model's answer is invalid; the large model's answer on the same row is used and both calls are paid.
Usage: python3 route_calib.py results/<small>.json results/<large>.json [--thresholds ...] [--out results/route__X]
       python3 route_calib.py results/<small>.json --calib   (calibration table only)"""
import json, sys, os, argparse, statistics, math
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, os.path.dirname(HERE))
import fw
def confidence(r):
    """Returns (value, kind). kind: 'self' = JSON confidence 0..1, 'logprob' = exp(first-token logprob) in 0..1."""
    raw = r.get("raw") or ""
    if raw.strip().startswith("{"):
        try:
            c = json.loads(raw).get("confidence")
            if isinstance(c, (int, float)): return float(c), "self"
        except Exception: pass
    lp = r.get("first_token_logprob")
    if lp is not None: return math.exp(lp), "logprob"
    return None, "none"
def cost(r, p): return (r["in_tokens"] * p[0] + r["out_tokens"] * p[1]) / 1e6
def calib(rows, edges=(0.0, 0.5, 0.8, 0.9, 0.95, 0.99, 1.0001)):
    out = []
    for lo, hi in zip(edges, edges[1:]):
        b = [r for r in rows if r["_conf"] is not None and lo <= r["_conf"] < hi]
        if b: out.append({"bucket": f"[{lo:.2f}, {min(hi,1):.2f}{')' if hi<1 else ']'}", "n": len(b), "accuracy": sum(r["correct"] for r in b) / len(b), "mean_conf": sum(r["_conf"] for r in b) / len(b)})
    nc = [r for r in rows if r["_conf"] is None]
    if nc: out.append({"bucket": "no confidence (invalid/empty)", "n": len(nc), "accuracy": sum(r["correct"] for r in nc) / len(nc), "mean_conf": None})
    return out
def main():
    ap = argparse.ArgumentParser(); ap.add_argument("small"); ap.add_argument("large", nargs="?")
    ap.add_argument("--thresholds", type=float, nargs="+", default=[0.5, 0.8, 0.9, 0.95]); ap.add_argument("--out"); ap.add_argument("--calib", action="store_true")
    a = ap.parse_args()
    S = json.load(open(a.small)); kinds = set()
    for r in S["rows"]:
        r["_conf"], k = confidence(r); kinds.add(k)
    print(f"{os.path.basename(a.small)}: confidence source {sorted(kinds)}")
    print("| confidence bucket | n | accuracy | mean confidence |\n|---|---|---|---|")
    for b in calib(S["rows"]):
        mc = "-" if b["mean_conf"] is None else f"{b['mean_conf']:.3f}"
        print(f"| {b['bucket']} | {b['n']} | {b['accuracy']:.1%} | {mc} |")
    if a.calib or not a.large: return
    L = json.load(open(a.large)); lrows = {r["id"]: r for r in L["rows"]}
    ps, pl = fw.PRICING[S["model"]], fw.PRICING[L["model"]]
    print(f"\nroute {S['model'].split('/')[-1]} ({S['tag']}) -> {L['model'].split('/')[-1]} ({L['tag']})")
    print("| threshold | escalated | accuracy | invalid | p50 s | p95 s | $/1k |\n|---|---|---|---|---|---|---|")
    for t in a.thresholds:
        rows, c, esc = [], 0.0, 0
        for r in S["rows"]:
            if r["id"] not in lrows: continue
            low = (r["_conf"] is None) or (r["_conf"] < t) or r["pred"] == "invalid"
            c += cost(r, ps); l = r["latency"]; pred = r["pred"]
            if low:
                esc += 1; lr = lrows[r["id"]]; c += cost(lr, pl); l += lr["latency"]; pred = lr["pred"]
            rows.append({"id": r["id"], "label": r["label"], "pred": pred, "correct": pred == r["label"], "escalated": low, "latency": l, "confidence": r["_conf"]})
        n = len(rows); lat = sorted(r["latency"] for r in rows)
        summ = {"model": f"route({S['model'].split('/')[-1]}->{L['model'].split('/')[-1]})", "prompt": f"{S['tag']}+route@{t}", "tag": f"route@{t}", "n": n, "seed": 0,
                "threshold": t, "confidence_source": sorted(kinds), "escalation_rate": esc / n, "accuracy": round(sum(r["correct"] for r in rows) / n, 4),
                "invalid_outputs": sum(r["pred"] == "invalid" for r in rows), "p50_latency_s": round(statistics.median(lat), 3), "p95_latency_s": round(lat[int(0.95 * (n - 1))], 3),
                "cost_per_1k_requests_usd": round(c / n * 1000, 4), "small_file": os.path.basename(a.small), "large_file": os.path.basename(a.large), "rows": rows}
        print(f"| {t} | {esc/n:.0%} | {summ['accuracy']:.1%} | {summ['invalid_outputs']} | {summ['p50_latency_s']:.2f} | {summ['p95_latency_s']:.2f} | {summ['cost_per_1k_requests_usd']:.3f} |")
        if a.out: json.dump(summ, open(f"{a.out}@{t}.json", "w"), indent=1)
if __name__ == "__main__": main()
