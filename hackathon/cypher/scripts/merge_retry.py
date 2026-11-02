"""Replace API-failed rows in a results file with rows from a retry run; recompute summary fields."""
import json, sys, statistics
main_p, retry_p = sys.argv[1], sys.argv[2]
d = json.load(open(main_p)); r = json.load(open(retry_p))
fix = {x["id"]: x for x in r["rows"] if not x["api_error"]}
d["rows"] = [fix.get(x["id"], x) if x["api_error"] else x for x in d["rows"]]
rows, n = d["rows"], d["n"]
pct = lambda xs, p: sorted(xs)[int(p * (len(xs) - 1))]
cnt = lambda s: sum(x["exec_status"] == s for x in rows)
d.update({"accuracy": round(cnt("correct") / n, 4), "accuracy_lenient": round(sum(x["lenient_status"] == "correct" for x in rows) / n, 4),
          "invalid_outputs": cnt("error"), "error_rate": round(cnt("error") / n, 4), "empty_rate": round(cnt("empty") / n, 4),
          "wrong_rate": round(cnt("wrong") / n, 4), "api_errors": sum(1 for x in rows if x["api_error"]),
          "truncated": sum(1 for x in rows if x["finish_reason"] == "length"),
          "p50_latency_s": round(statistics.median([x["latency"] for x in rows]), 3), "p95_latency_s": round(pct([x["latency"] for x in rows], .95), 3),
          "p50_wall_s_incl_retries": round(statistics.median([x["wall_s"] for x in rows]), 3), "p95_wall_s_incl_retries": round(pct([x["wall_s"] for x in rows], .95), 3),
          "in_tokens": d["in_tokens"] + r["in_tokens"], "out_tokens": d["out_tokens"] + r["out_tokens"],
          "reasoning_tokens": d["reasoning_tokens"] + r["reasoning_tokens"], "merged_retry_from": retry_p, "retry_rows_fixed": len(fix)})
pin, pout = 0.05, 0.20
d["cost_total_usd"] = round((d["in_tokens"] * pin + d["out_tokens"] * pout) / 1e6, 4)  # includes failed+retried calls billed
d["cost_per_1k_requests_usd"] = round(d["cost_total_usd"] / n * 1000, 4)
for key, field in (("by_graph", "graph"), ("by_tier", "tier")):
    for k in d[key]:
        rs = [x for x in rows if x[field] == k]
        d[key][k] = {"n": len(rs), "accuracy": round(sum(x["correct"] for x in rs) / len(rs), 4),
                     "accuracy_lenient": round(sum(x["lenient_status"] == "correct" for x in rs) / len(rs), 4),
                     "error": sum(x["exec_status"] == "error" for x in rs), "empty": sum(x["exec_status"] == "empty" for x in rs)}
json.dump(d, open(main_p, "w"), indent=1, default=str)
print(f"fixed {len(fix)} rows; acc {d['accuracy']} lenient {d['accuracy_lenient']} err {d['error_rate']} api_errors left {d['api_errors']}")
