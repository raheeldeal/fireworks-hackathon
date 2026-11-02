#!/usr/bin/env python3
"""Re-run only the rows of a results file that failed for infrastructure reasons (HTTP 429 after retries, or
finish_reason == "length" i.e. reasoning exhausted max_tokens) and write <name>_retry.json. The original file is
left untouched. Re-run uses the same model/prompt/shots/json/confidence settings, max_tokens 8192, 2 workers,
slower backoff. Every call is logged to ledger.csv. Usage: python3 patch_rows.py results/glm-5p3_v1_plain.json"""
import json, os, random, statistics, sys, time
import run_eval
from run_eval import PRICING, SHORT, build_messages, pick_shots, ledger_add, ledger_total, SPEND_CAP, fireworks_call, CONF_RE
from score import score
from concurrent.futures import ThreadPoolExecutor

HERE = os.path.dirname(os.path.abspath(__file__))


def patch(path, max_tokens=8192, workers=2):
    d = json.load(open(path))
    test = {json.loads(l)["id"]: json.loads(l) for l in open(os.path.join(HERE, "data", "test.jsonl"))}
    cfg = d["prompt"]
    pfile = "v2_rubric" if cfg.startswith("v2_rubric") else "v1_plain"
    system_prompt = open(os.path.join(HERE, "prompts", pfile + ".txt")).read().strip()
    conf = "_conf" in cfg
    if conf:
        system_prompt += "\n\nAfter the code block, add one final line: `Confidence: NN` where NN is 0-100, your probability that the fixed function passes all hidden tests."
    shots = pick_shots(d.get("shots", 0))
    json_mode = "_json" in cfg
    todo = [r for r in d["rows"] if r.get("api_error") or r.get("finish_reason") == "length"]
    print(f"{os.path.basename(path)}: re-running {len(todo)} of {d['n']} rows (ledger ${ledger_total():.3f})")

    def work(r):
        if ledger_total() >= SPEND_CAP:
            return r
        ex = test[r["id"]]
        msgs = build_messages(system_prompt, shots, ex)
        for attempt in range(4):
            try:
                raw, lat, ti, to, rt, finish, _ = fireworks_call(d["model"], msgs, max_tokens, json_mode, None, timeout=300)
                err = ""
                break
            except Exception as e:
                err = str(e)[:200]; raw, lat, ti, to, rt, finish = "", 0.0, 0, 0, 0, "error"
                time.sleep(20 * (attempt + 1))
        cost = ledger_add(d["model"], ti, to, f"{cfg}_retry:{ex['id']}")
        sc = score(raw, ex)
        c = None
        if conf:
            m = CONF_RE.findall(raw); c = int(m[-1]) if m else None
        return {**r, "raw": raw, "status": sc["status"], "correct": bool(sc["correct"]), "invalid": bool(sc["invalid"]),
                "detail": sc["detail"][:300], "latency": lat, "in_tokens": ti, "out_tokens": to, "reasoning_tokens": rt,
                "finish_reason": finish, "confidence": c, "api_error": err, "cost": cost, "retried": True}

    with ThreadPoolExecutor(max_workers=workers) as pool:
        new = {r["id"]: r for r in pool.map(work, todo)}
    rows = [new.get(r["id"], r) for r in d["rows"]]
    for r in rows:
        flag = "✓" if r["correct"] else ("!" if r["invalid"] else "✗")
        if r.get("retried"):
            print(f"  {flag} {r['id']:11s} {r['status']:10s} {r['latency']:5.1f}s out={r['out_tokens']} rt={r['reasoning_tokens']} {r['api_error'][:40]}")
    n = len(rows); lats = sorted(r["latency"] for r in rows if r["latency"] > 0) or [0.0]
    pin, pout = PRICING[d["model"]]
    in_tok = sum(r["in_tokens"] for r in rows); out_tok = sum(r["out_tokens"] for r in rows)
    cost_total = (in_tok * pin + out_tok * pout) / 1e6
    out = {**d, "prompt": cfg + "_retry", "retried_rows": len(todo),
           "accuracy": round(sum(r["correct"] for r in rows) / n, 4), "invalid_outputs": sum(r["invalid"] for r in rows),
           "api_errors": sum(1 for r in rows if r["api_error"]),
           "p50_latency_s": round(statistics.median(lats), 3), "p95_latency_s": round(lats[int(0.95 * (len(lats) - 1))], 3),
           "cost_per_1k_requests_usd": round(cost_total / n * 1000, 4), "avg_in_tokens": round(in_tok / n, 1),
           "avg_out_tokens": round(out_tok / n, 1), "avg_reasoning_tokens": round(sum(r["reasoning_tokens"] for r in rows) / n, 1),
           "run_cost_usd": round(cost_total, 4), "rows": rows}
    op = path.replace(".json", "_retry.json")
    json.dump(out, open(op, "w"), indent=2)
    print(f"  -> {os.path.basename(op)}: accuracy {out['accuracy']:.1%} invalid {out['invalid_outputs']} api_err {out['api_errors']} ${out['cost_per_1k_requests_usd']:.3f}/1k | ledger ${ledger_total():.3f}")


if __name__ == "__main__":
    for p in sys.argv[1:]:
        patch(p)
