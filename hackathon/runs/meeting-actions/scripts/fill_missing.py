#!/usr/bin/env python3
"""Re-run only the test rows missing from a results file (after transient errors) and recompute the summary.
    python3 scripts/fill_missing.py results/<file>.json [--limit N]   (limit = intended n, e.g. 70 for kimi)
"""
import argparse, json, os, random, statistics, sys
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "scripts")); sys.path.insert(0, ROOT)
import fw, score as S
import run_eval as R

ap = argparse.ArgumentParser(); ap.add_argument("path"); ap.add_argument("--limit", type=int, default=0); a = ap.parse_args()
d = json.load(open(a.path))
examples = R.load_jsonl(os.path.join(ROOT, "data", "test.jsonl"))
if d.get("seed"):
    random.Random(d["seed"]).shuffle(examples)
if a.limit:
    examples = examples[: a.limit]
have = {r["id"] for r in d["rows"]}
missing = [e for e in examples if e["id"] not in have]
print(f"{len(have)} present, {len(missing)} missing")
pname = d["prompt"]; json_mode = pname.endswith("_json"); base = pname[:-5] if json_mode else pname
sp = open(os.path.join(ROOT, "prompts", base + ".txt")).read()
for e in missing:
    try:
        d["rows"].append(R.one(d["model"], sp, e, 1024, R.MODEL_EXTRA.get(d["model"]), json_mode, f"{d['model'].split('/')[-1]}:{pname}:fill"))
    except Exception as ex:
        print("ERR", e["id"], str(ex)[:200])
rows = sorted(d["rows"], key=lambda r: r["id"]); d["rows"] = rows
agg = S.aggregate([r["score"] for r in rows]); lats = sorted(r["latency"] for r in rows); n = len(rows)
d.update({"n": n, "accuracy": agg["f1"], "precision": agg["precision"], "recall": agg["recall"], "f1": agg["f1"], "due_acc": agg["due_acc"],
          "exact_row_acc": agg["exact_row_acc"], "invalid_outputs": agg["invalid"], "p50_latency_s": round(statistics.median(lats), 3),
          "p95_latency_s": round(lats[int(0.95 * (n - 1))], 3), "cost_per_1k_requests_usd": round(sum(r["cost"] for r in rows) / n * 1000, 4),
          "errors": len(examples) - n})
json.dump(d, open(a.path, "w"), indent=1)
print(f"{d['model'].split('/')[-1]} + {pname}: n={n} F1 {agg['f1']:.3f} P {agg['precision']:.3f} R {agg['recall']:.3f} due {agg['due_acc']:.3f} invalid {agg['invalid']} ${d['cost_per_1k_requests_usd']:.3f}/1k | ledger ${fw.ledger_total():.3f}")
