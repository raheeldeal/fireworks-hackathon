#!/usr/bin/env python3
"""Re-run only the rows of a results file whose call ended in an HTTP/transport error (finish starts with 'error'),
with the run's own settings, and rewrite the summary. Usage: python3 fix_errors.py results/<run>.json"""
import json, statistics, sys
import run_eval, score
path = sys.argv[1]
d = json.load(open(path))
bad = [r for r in d["rows"] if str(r.get("finish", "")).startswith("error")]
print(f"{path}: {len(bad)} error rows of {d['n']}")
if bad:
    system = run_eval.build_system(d.get("prompt_path", f"prompts/{d['prompt']}.txt"), d.get("fewshot", 0), d["seed"])
    for r in bad:
        res = run_eval.call(d["model"], system, r["text"], d.get("max_tokens", 2048), d.get("json_mode", False), True,
                            d.get("reasoning_effort"), d.get("no_think", False))
        run_eval.ledger_add(d["model"], res["in"], res["out"], "fix-" + path.split("/")[-1])
        pred = score.normalize(res["raw"])
        r.update({"raw": res["raw"][:2000], "pred": pred, "correct": pred == r["label"], "latency": round(res["latency"], 3),
                  "in_tokens": res["in"], "out_tokens": res["out"], "reasoning_tokens": res["reasoning_tokens"],
                  "finish": res["finish"], "confidence": res["confidence"]})
        print(("✓" if r["correct"] else "✗"), r["label"], "->", pred, r["finish"])
    rows = d["rows"]; m = score.metrics(rows); lat = sorted(r["latency"] for r in rows)
    ti, to = sum(r["in_tokens"] for r in rows), sum(r["out_tokens"] for r in rows)
    pi, po = run_eval.PRICING.get(d["model"], (0, 0)); cost = (ti * pi + to * po) / 1e6
    d.update({"accuracy": m["accuracy"], "macro_f1": m["macro_f1"], "invalid_outputs": m["invalid"],
              "p50_latency_s": round(statistics.median(lat), 3), "p95_latency_s": round(lat[int(0.95 * (len(lat) - 1))], 3),
              "in_tokens": ti, "out_tokens": to, "cost_usd": round(cost, 4), "cost_per_1k_requests_usd": round(cost / m["n"] * 1000, 4)})
    json.dump(d, open(path, "w"), indent=1)
    print(f"fixed: acc {m['accuracy']:.1%} invalid {m['invalid']}")
