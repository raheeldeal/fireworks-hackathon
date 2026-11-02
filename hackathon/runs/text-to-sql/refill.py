#!/usr/bin/env python3
"""Re-request only the rows whose API call failed (429/5xx after retries) in an existing results file, then
recompute the summary. A rate-limit error is not a model error, so leaving those rows as 'invalid' would be unfair.
Usage: python3 refill.py results/<file>.json [more files]"""
import json, os, statistics, sys
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
from run_eval import fireworks_call, PRICING, DB_ROOT, ledger_add
from score import score
for path in sys.argv[1:]:
    d = json.load(open(path))
    todo = [r for r in d["rows"] if r.get("api_error")]
    if not todo:
        print(f"{os.path.basename(path)}: no api errors"); continue
    prompt_file = os.path.join(HERE, "prompts", d["prompt"].replace("_nothink", "").replace("_lp", "").replace("_json", "") + ".txt")
    if d["prompt"].endswith("_json"): prompt_file = os.path.join(HERE, "prompts", "v2_rubric_json.txt")
    system_prompt = open(prompt_file).read().strip()
    test = {r["id"]: r for r in (json.loads(l) for l in open(os.path.join(HERE, "data", "test.jsonl")))}
    ti = to = 0
    for r in todo:
        ex = test[r["id"]]
        raw, lat, a, b, reasoning, lp, err = fireworks_call(d["model"], system_prompt, ex, 1024, d.get("extra") or {})
        ti += a; to += b
        s = score(raw, ex["gold_sql"], os.path.join(DB_ROOT, ex["db_id"], ex["db_id"] + ".sqlite"))
        r.update({"raw": raw, "pred_sql": s["pred_sql"], "correct": s["exec_match"], "exact": s["exact_match"], "invalid": s["invalid"],
                  "error": s["error"] or err, "latency": lat, "in_tokens": a, "out_tokens": b, "reasoning_tokens": reasoning, "mean_logprob": lp, "api_error": err})
        print(("✓" if s["exec_match"] else "✗"), r["id"], err or "")
    pi, po = PRICING.get(d["model"], (0, 0)); cost = (ti * pi + to * po) / 1e6
    ledger_add(d["model"], ti, to, cost, f"refill {os.path.basename(path)} rows={len(todo)}")
    rows = d["rows"]; n = len(rows); lats = sorted(r["latency"] for r in rows if r["latency"] > 0) or [0]
    d["accuracy"] = round(sum(r["correct"] for r in rows) / n, 4); d["exact_match"] = round(sum(r["exact"] for r in rows) / n, 4)
    d["invalid_outputs"] = sum(r["invalid"] for r in rows); d["api_errors"] = sum(1 for r in rows if r["api_error"])
    d["p50_latency_s"] = round(statistics.median(lats), 3); d["p95_latency_s"] = round(lats[int(0.95 * (len(lats) - 1))], 3)
    d["in_tokens"] = sum(r["in_tokens"] for r in rows); d["out_tokens"] = sum(r["out_tokens"] for r in rows)
    d["cost_total_usd"] = round((d["in_tokens"] * pi + d["out_tokens"] * po) / 1e6, 5)
    d["cost_per_1k_requests_usd"] = round(d["cost_total_usd"] / n * 1000, 4)
    d["refilled_api_errors"] = len(todo)
    json.dump(d, open(path, "w"), indent=1)
    print(f"{os.path.basename(path)}: refilled {len(todo)} rows -> acc {d['accuracy']:.1%}, invalid {d['invalid_outputs']}, api_err {d['api_errors']}")
