#!/usr/bin/env python3
"""Re-run only the rows whose call errored (HTTP/network) in a results file and recompute the summary in place.
Model behaviour is untouched: rows that returned a response are never re-called. Usage: python3 retry_errors.py results/x.json [...]"""
import json, sys, statistics, os, re
import fw, score as sc
from retrieve import Retriever
from run_eval import build_system, catalog_text
HERE = os.path.dirname(os.path.abspath(__file__))
catalog = json.load(open(os.path.join(HERE, "data", "catalog.json")))
for p in sys.argv[1:]:
    d = json.load(open(p)); tag = d["tag"]; cfg = d["prompt"]
    errs = [r for r in d["rows"] if str(r["finish_reason"]).startswith("error")]
    if not errs: print(p, "no errors"); continue
    prompt_name = cfg.split("+")[0]; template = open(os.path.join(HERE, "prompts", prompt_name + ".txt")).read()
    m = re.search(r"\+retr(\d+)", cfg); retr = Retriever(catalog) if m else None; k = int(m.group(1)) if m else 0
    shots = []
    if "+5shot" in cfg:
        import random; train = [json.loads(l) for l in open(os.path.join(HERE, "data", "train.jsonl"))]; shots = random.Random(42).sample(train, 5)
    extra = {}
    m = re.search(r"\+r(none|low|high)", cfg)
    if m: extra["reasoning_effort"] = m.group(1)
    if "+json" in cfg or prompt_name == "v4_json": extra["response_format"] = {"type": "json_object"}
    if any("first_token_logprob" in r for r in d["rows"]): extra.update({"logprobs": True, "top_logprobs": 5})
    for r in errs:
        tools = retr.top(r["text"], k) if retr else catalog
        msgs = [{"role": "system", "content": build_system(template, tools, shots)}, {"role": "user", "content": r["text"]}]
        res = fw.chat(d["model"], msgs, max_tokens=1024, extra=extra or None, note=f"retry:{tag}")
        s = sc.score(res["content"], r["label"])
        r.update({"raw": res["content"], "pred": s["pred"], "ranked": s["ranked"], "correct": s["top1"], "top3": s["top3"], "latency": round(res["latency"], 3),
                  "in_tokens": res["in_tokens"], "out_tokens": res["out_tokens"], "reasoning_tokens": res["reasoning_tokens"], "finish_reason": res["finish_reason"], "retried": True})
        if "first_token_logprob" in r:
            try:
                lp = res["raw"]["choices"][0]["logprobs"]["content"]; toks = [t for t in lp if t.get("token", "").strip()]
                r["first_token_logprob"] = toks[0]["logprob"] if toks else None; r["sum_logprob"] = sum(t["logprob"] for t in lp)
            except Exception: pass
        print(("✓" if r["correct"] else "✗"), r["label"], "->", r["pred"])
    rows = d["rows"]; n = len(rows); lat = sorted(r["latency"] for r in rows)
    tin = sum(r["in_tokens"] for r in rows); tout = sum(r["out_tokens"] for r in rows); pi, po = fw.PRICING[d["model"]]
    cost = (tin * pi + tout * po) / 1e6
    d.update({"accuracy": round(sum(r["correct"] for r in rows) / n, 4), "top3_accuracy": round(sum(r["top3"] for r in rows) / n, 4),
              "invalid_outputs": sum(r["pred"] == "invalid" for r in rows), "errors": sum(str(r["finish_reason"]).startswith("error") for r in rows),
              "p50_latency_s": round(statistics.median(lat), 3), "p95_latency_s": round(lat[int(0.95 * (n - 1))], 3),
              "cost_per_1k_requests_usd": round(cost / n * 1000, 4), "in_tokens": tin, "out_tokens": tout,
              "reasoning_tokens": sum(r["reasoning_tokens"] for r in rows), "avg_in_tokens": round(tin / n, 1), "avg_out_tokens": round(tout / n, 1),
              "retried_errors": len(errs)})
    if d.get("catalog_cost_share") is not None and d.get("catalog_tokens_est"):
        d["catalog_cost_share"] = round(d["catalog_tokens_est"] * n * pi / 1e6 / cost, 3)
    json.dump(d, open(p, "w"), indent=1)
    print(f"{p}: retried {len(errs)} -> acc {d['accuracy']:.3f} invalid {d['invalid_outputs']} errors {d['errors']}")
