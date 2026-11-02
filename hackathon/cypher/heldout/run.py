#!/usr/bin/env python3
"""Score one model on the held-out graph with the main exam's prompt (prompts/v1_plain.txt, system=schema prompt, user=question).
API models: run_eval.fireworks_call (temperature 0). Muse models: train/rl.py Training-API sampler (temperature 0, to=user prefill).
Scored with score_v2 (correct/accuracy) and score v1 (kept as *_v1). Spend goes to heldout/ledger.csv, cap $3.

  PY="env PYTHONPATH=train/.pylib ../runs/regex/venv311/bin/python"   # from hackathon/cypher
  $PY heldout/run.py --kind api  --model accounts/fireworks/models/glm-5p3-flash --out heldout/results/glm-5p3-flash.json
  $PY heldout/run.py --kind muse --model base --out heldout/results/muse_base.json
"""
import argparse, json, os, sys, statistics, logging, glob
from concurrent.futures import ThreadPoolExecutor
HERE = os.path.dirname(os.path.abspath(__file__)); CY = os.path.dirname(HERE)
sys.path.insert(0, CY); sys.path.insert(0, os.path.join(CY, "train"))
logging.getLogger("neo4j").setLevel(logging.ERROR)
from executor import execute
import score as S
LEDGER = os.path.join(HERE, "ledger.csv"); CAP = 3.00

ap = argparse.ArgumentParser()
ap.add_argument("--kind", choices=["api", "muse"], required=True)
ap.add_argument("--model", required=True)
ap.add_argument("--out", required=True)
ap.add_argument("--limit", type=int, default=0)
ap.add_argument("--workers", type=int, default=8)
ap.add_argument("--extra", default="{}")
args = ap.parse_args()

data = glob.glob(os.path.join(HERE, "test_*.jsonl"))[0]
graph = os.path.basename(data)[5:-6]
rows = [json.loads(l) for l in open(data)]
if args.limit:
    rows = rows[: args.limit]
unl = json.load(open(os.path.join(HERE, f"gold_unlimited_{graph}.json")))
template = open(os.path.join(CY, "prompts", "v1_plain.txt")).read()

if args.kind == "api":
    import run_eval as R
    R.LEDGER, R.CAP_USD = LEDGER, CAP
    pin, pout = R.PRICING[args.model]
    if R.ledger_total() >= CAP: sys.exit("cap")
    extra = json.loads(args.extra)
    def call(ex):
        r = R.fireworks_call(args.model, template.replace("{schema}", ex["schema"]), ex["question"], 4096, extra, 180)
        return {"raw": r["raw"], "text": r["raw"], "latency": r["latency"], "in": r["in"], "out": r["out"], "reasoning": r["reasoning"],
                "finish": r["finish"], "api_error": r["api_error"]}
    with ThreadPoolExecutor(args.workers) as p:
        outs = list(p.map(call, rows))
    tin, tout = sum(o["in"] for o in outs), sum(o["out"] for o in outs)
    cost = (tin * pin + tout * pout) / 1e6
    R.ledger_add(args.model, tin, tout, cost, f"heldout {graph} n={len(rows)}")
    model_name, req = args.model, extra
else:
    import rl
    rl.LEDGER, rl.CAP = LEDGER, CAP
    tok = rl.get_tokenizer()
    sampler = rl.make_sampler(rl.service_client(), tok, args.model)
    recs = rl.sample_rows(tok, sampler, rows, 1, 0.0, 400, f"heldout {graph} {os.path.basename(args.out)}", args.workers)
    outs = []
    for rec in recs:
        c = rec["cands"][0] if rec["cands"] else {"raw": "", "text": "", "out_tokens": 0, "stop": "error"}
        outs.append({"raw": c["raw"][:2000], "text": c["text"], "latency": rec["latency"], "in": rec["in_tokens"], "out": c["out_tokens"],
                     "reasoning": 0, "finish": c["stop"], "api_error": rec["api_error"]})
    tin, tout = sum(o["in"] for o in outs), sum(o["out"] for o in outs)
    cost = (tin * rl.PRICE_PREFILL + tout * rl.PRICE_SAMPLE) / 1e6
    model_name = rl.BASE_MODEL if args.model == "base" else f"{rl.BASE_MODEL} + LoRA {args.model}"
    req = {"sampler": "serverless training", "temperature": 0, "prefill": "to=user (reasoning off)"}


def score_one(pair):
    ex, o = pair
    pred = S.clean_pred(o["text"])
    res = execute(graph, pred) if pred else {"ok": False, "rows": [], "columns": [], "error": "no query", "secs": 0}
    gold = {"ok": True, **ex["gold_result"]}
    v1 = S.score(gold, res, ex["cypher"])
    v2 = S.score_v2(gold, res, ex["cypher"], unl.get(ex["id"]))
    return {"id": ex["id"], "graph": graph, "tier": ex["complexity"]["tier"], "complexity": ex["complexity"], "question": ex["question"],
            "gold_cypher": ex["cypher"], "raw": o["raw"], "pred_cypher": pred, "exec_status": v2, "exec_status_v1": v1, "exec_status_v2": v2,
            "lenient_status": S.score_lenient(gold, res, ex["cypher"]), "exec_error": res.get("error"), "pred_n_rows": len(res["rows"]),
            "pred_rows_head": res["rows"][:5], "correct": v2 == "correct", "correct_v1": v1 == "correct", "correct_v2": v2 == "correct",
            "pred": v2, "label": "correct", "latency": round(o["latency"], 3), "in_tokens": o["in"], "out_tokens": o["out"],
            "reasoning_tokens": o["reasoning"], "finish_reason": o["finish"], "api_error": o["api_error"]}

with ThreadPoolExecutor(8) as p:
    out_rows = list(p.map(score_one, zip(rows, outs)))
n = len(out_rows)
acc = lambda rs, k="correct_v2": round(sum(r[k] for r in rs) / len(rs), 4) if rs else None
summary = {"model": model_name, "prompt": "v1_plain", "scorer": "score_v2 (audit/SCORING.md)", "n": n, "graph": graph,
           "accuracy": acc(out_rows), "accuracy_v2": acc(out_rows), "accuracy_v1": acc(out_rows, "correct_v1"),
           "accuracy_lenient": acc(out_rows, "lenient_status") if False else round(sum(r["lenient_status"] == "correct" for r in out_rows) / n, 4),
           "error_rate": round(sum(r["exec_status"] == "error" for r in out_rows) / n, 4),
           "empty_rate": round(sum(r["exec_status"] == "empty" for r in out_rows) / n, 4),
           "wrong_rate": round(sum(r["exec_status"] == "wrong" for r in out_rows) / n, 4),
           "p50_latency_s": round(statistics.median(r["latency"] for r in out_rows), 3),
           "cost_total_usd": round(cost, 4), "in_tokens": tin, "out_tokens": tout,
           "api_errors": sum(1 for r in out_rows if r["api_error"]), "request_extra": req, "checkpoint": args.model,
           "test_file": os.path.relpath(data, CY), "test_sha256": open(os.path.join(HERE, "HASH")).read().split()[0],
           "by_tier_v2": {t: {"n": len(rs), "accuracy_v1": acc(rs, "correct_v1"), "accuracy_v2": acc(rs)}
                          for t in ("easy", "medium", "hard") for rs in [[r for r in out_rows if r["tier"] == t]] if rs},
           "rows": out_rows}
os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
json.dump(summary, open(args.out, "w"), indent=1, default=str)
print(f"{os.path.basename(args.out)}: v2 {summary['accuracy']:.1%} v1 {summary['accuracy_v1']:.1%} err {summary['error_rate']:.1%} "
      f"empty {summary['empty_rate']:.1%} apierr {summary['api_errors']} cost ${cost:.4f} | tiers {summary['by_tier_v2']}")
