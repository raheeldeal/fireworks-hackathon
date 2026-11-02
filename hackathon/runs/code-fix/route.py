#!/usr/bin/env python3
"""Routing: small model answers; escalate to the large model when the small answer is invalid or low-confidence.

Both models were already run at temperature 0 on the same rows, so routing is computed offline from the two
results files (no extra inference cost, identical answers to what a live router would get). Reported cost and
latency are the small call plus, for escalated rows, the large call.

Confidence signals (--signal):
  verify   : run the small model's fix against the ONE visible failing assert from the prompt (free, deterministic).
             Escalate if invalid, or if that assert still fails. threshold is ignored (binary).
  self     : the small model's self-reported `Confidence: NN` line (needs a --confidence run). Escalate if
             invalid or confidence < threshold. Sweep thresholds with --thresholds 50,70,90.
  tokens   : escalate if invalid or the small model used more than `threshold` completion tokens (long thinking =
             uncertainty proxy). Sweep e.g. --thresholds 400,800,1600.
Usage:
  python3 route.py --small results/glm-5p3-flash_v1_plain.json --large results/glm-5p3_v1_plain.json --signal verify
"""
import argparse, json, os, re, statistics
from sandbox import run_program
from score import extract_code, strip_trailing_tests
from run_eval import PRICING, SHORT

HERE = os.path.dirname(os.path.abspath(__file__))


def visible_assert_passes(row_small, test_row):
    """Does the small model's code pass the single assert shown in the failing-test output?"""
    asserts = [l.strip() for l in test_row["error"].splitlines() if l.strip().startswith("assert")]
    if not asserts:
        return None  # timeout rows: nothing visible to check
    code = strip_trailing_tests(extract_code(row_small["raw"]))
    prog = test_row["test_program_prefix"] + code + "\n" + asserts[-1] + "\n"
    return run_program(prog, timeout=10)[0] == "pass"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--small", required=True); ap.add_argument("--large", required=True)
    ap.add_argument("--signal", choices=["verify", "self", "tokens"], default="verify")
    ap.add_argument("--thresholds", default="0")
    ap.add_argument("--data", default=os.path.join(HERE, "data", "test.jsonl"))
    a = ap.parse_args()
    S, L = json.load(open(a.small)), json.load(open(a.large))
    test = {json.loads(l)["id"]: json.loads(l) for l in open(a.data)}
    srows = {r["id"]: r for r in S["rows"]}; lrows = {r["id"]: r for r in L["rows"]}
    ids = [i for i in srows if i in lrows]
    print(f"{len(ids)} rows in both files; small={SHORT[S['model']]} large={SHORT[L['model']]}")
    verify_cache = {}
    if a.signal == "verify":
        for i in ids:
            verify_cache[i] = visible_assert_passes(srows[i], test[i])
    ps_in, ps_out = PRICING[S["model"]]; pl_in, pl_out = PRICING[L["model"]]
    for thr in [float(t) for t in a.thresholds.split(",")]:
        rows, lats, cost = [], [], 0.0
        for i in ids:
            s = srows[i]
            if s["invalid"]:
                esc = True
            elif a.signal == "verify":
                esc = verify_cache[i] is False
            elif a.signal == "self":
                esc = s.get("confidence") is None or s["confidence"] < thr
            else:
                esc = s["out_tokens"] > thr
            pick = lrows[i] if esc else s
            lat = s["latency"] + (lrows[i]["latency"] if esc else 0)
            c = (s["in_tokens"] * ps_in + s["out_tokens"] * ps_out) / 1e6
            if esc:
                c += (lrows[i]["in_tokens"] * pl_in + lrows[i]["out_tokens"] * pl_out) / 1e6
            cost += c; lats.append(lat)
            rows.append({**pick, "escalated": esc, "latency": lat, "id": i})
        n = len(rows); lats.sort()
        tag = f"route_{a.signal}" + (f"_{int(thr)}" if a.signal != "verify" else "")
        summary = {"model": f"{S['model']}->{SHORT[L['model']]}", "prompt": f"{S['prompt']}_{tag}", "mock": False, "n": n,
                   "accuracy": round(sum(r["correct"] for r in rows) / n, 4), "invalid_outputs": sum(r["invalid"] for r in rows),
                   "escalation_rate": round(sum(r["escalated"] for r in rows) / n, 4), "threshold": thr,
                   "p50_latency_s": round(statistics.median(lats), 3), "p95_latency_s": round(lats[int(0.95 * (n - 1))], 3),
                   "cost_per_1k_requests_usd": round(cost / n * 1000, 4), "run_cost_usd": round(cost, 4),
                   "small_file": os.path.basename(a.small), "large_file": os.path.basename(a.large), "rows": rows}
        out = os.path.join(HERE, "results", f"ROUTE_{SHORT[S['model']]}_to_{SHORT[L['model']]}_{S['prompt']}_{tag}.json")
        json.dump(summary, open(out, "w"), indent=2)
        print(f"{tag:22s} acc {summary['accuracy']:.1%} | escalated {summary['escalation_rate']:.1%} | p50 {summary['p50_latency_s']}s | ${summary['cost_per_1k_requests_usd']:.3f}/1k -> {os.path.basename(out)}")


if __name__ == "__main__":
    main()
