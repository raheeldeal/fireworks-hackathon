#!/usr/bin/env python3
"""Offline routing: small model answers; escalate to the large model when the small answer is invalid or
low-confidence. Uses cached per-row results, so no extra API calls. Writes results/route_<small>_<large>_t<thr>.json.

Confidence signal (no logprobs needed): the small model is asked (v3 prompt) to add a top-level
"confidence" 0-1 per item, or we use a proxy: escalate if invalid, or if the number of items is 0,
or if any item has an empty/very short task, or if the min self-reported confidence < threshold.

    python3 scripts/route.py results/glm-5p3-flash_v2_rubric.json results/glm-5p3_v1_plain.json --thresholds 0.5 0.7 0.9
"""
import argparse, json, os, statistics, sys
sys.path.insert(0, os.path.dirname(__file__))
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__)))); import score as S


def confidence(row):
    """Return a confidence in [0,1] for a small-model row; 0 means 'definitely escalate'."""
    if not row["score"]["valid"]:
        return 0.0
    pred = row["pred"] or []
    if len(pred) == 0:
        return 0.0
    confs = []
    for p in pred:
        if not str(p.get("task", "")).strip() or not str(p.get("owner", "")).strip():
            return 0.0
        c = p.get("confidence")
        if isinstance(c, (int, float)):
            confs.append(float(c))
    return min(confs) if confs else 1.0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("small"); ap.add_argument("large")
    ap.add_argument("--filter", action="store_true", help="drop low-confidence items instead of escalating the row")
    ap.add_argument("--thresholds", nargs="+", type=float, default=[0.01, 0.5, 0.7, 0.9])
    ap.add_argument("--outdir", default=os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "results"))
    a = ap.parse_args()
    small, large = json.load(open(a.small)), json.load(open(a.large))
    L = {r["id"]: r for r in large["rows"]}
    for thr in a.thresholds:
        rows, esc = [], 0
        for r in small["rows"]:
            c = confidence(r)
            if a.filter:  # item-level: drop items whose self-reported confidence is below thr, no escalation
                orig = r["pred"] or []
                pred = [p for p in orig if not isinstance(p.get("confidence"), (int, float)) or float(p["confidence"]) >= thr]
                sc = S.score_rows(r["gold"], json.dumps(pred)) if r["score"]["valid"] else r["score"]
                rows.append({**r, "pred": pred, "score": sc, "escalated": False, "small_conf": c, "dropped": len(orig) - len(pred)})
                esc += len(orig) - len(pred)
                continue
            if c < thr and r["id"] in L:
                lr = dict(L[r["id"]]); lr = {**lr, "latency": r["latency"] + lr["latency"], "cost": r["cost"] + lr["cost"], "escalated": True, "small_conf": c}
                rows.append(lr); esc += 1
            else:
                rows.append({**r, "escalated": False, "small_conf": c})
        agg = S.aggregate([r["score"] for r in rows]); n = len(rows)
        lats = sorted(r["latency"] for r in rows)
        mode = "filter" if a.filter else "route"
        name = f"{mode}({small['model'].split('/')[-1]}" + ("" if a.filter else f"->{large['model'].split('/')[-1]}") + ")"
        out = {"model": name, "prompt": f"{small['prompt']}_thr{thr}",
               "mock": False, "n": n, "seed": 0, "threshold": thr, "escalated": esc, "escalation_rate": round(esc / n, 3),
               "accuracy": agg["f1"], **agg, "invalid_outputs": agg["invalid"], "p50_latency_s": round(statistics.median(lats), 3), "p95_latency_s": round(lats[int(0.95 * (n - 1))], 3),
               "cost_per_1k_requests_usd": round(sum(r["cost"] for r in rows) / n * 1000, 4), "rows": rows}
        tgt = "" if a.filter else large['model'].split('/')[-1] + "_"
        p = os.path.join(a.outdir, f"{mode}_{small['model'].split('/')[-1]}_{tgt}{small['prompt']}_t{thr}.json")
        json.dump(out, open(p, "w"), indent=1)
        print(f"thr {thr}: F1 {agg['f1']:.3f} P {agg['precision']:.3f} R {agg['recall']:.3f} {'dropped items' if a.filter else 'escalated rows'} {esc}/{n} ${out['cost_per_1k_requests_usd']:.3f}/1k p50 {out['p50_latency_s']}s -> {os.path.basename(p)}")


if __name__ == "__main__":
    main()
