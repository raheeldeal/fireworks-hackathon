#!/usr/bin/env python3
"""Run one model + one prompt config over data/test.jsonl; write results/<name>.json (same shape as hackathon/eval/run_eval.py plus field metrics).
Usage: python3 run_eval.py --model accounts/fireworks/models/glm-5p3-flash --prompt prompts/v1_plain.txt [--json-mode] [--limit 100] [--seed 7] [--workers 4]
"""
import argparse, json, os, random, statistics, sys, time
from concurrent.futures import ThreadPoolExecutor
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import fw, score as sc

HERE = os.path.dirname(os.path.abspath(__file__))
SCHEMA = json.load(open(os.path.join(HERE, "schema.json")))


def load_jsonl(p):
    return [json.loads(l) for l in open(p) if l.strip()]


def run_one(model, system_prompt, ex, json_mode, max_tokens):
    rf = {"type": "json_schema", "json_schema": {"name": "product", "schema": SCHEMA}} if json_mode else None
    try:
        content, reasoning, lat, ti, to, fin = fw.chat(model, [{"role": "system", "content": system_prompt}, {"role": "user", "content": ex["text"]}],
                                                       max_tokens=max_tokens, temperature=0, response_format=rf, note="eval")
    except fw.CapReached:
        raise
    except Exception as e:
        content, reasoning, lat, ti, to, fin = "", "", 0.0, 0, 0, f"error: {e}"
    r = sc.score(content, ex["gold"])
    return {"id": ex["id"], "text": ex["text"], "gold": ex["gold"], "raw": content, "pred": r["parsed"], "valid": r["valid"], "problems": r["problems"],
            "fields": r["fields"], "correct": r["all_correct"], "n_correct": r["n_correct"], "latency": lat, "in_tok": ti, "out_tok": to, "finish": fin}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", required=True)
    ap.add_argument("--prompt", required=True)
    ap.add_argument("--data", default=os.path.join(HERE, "data", "test.jsonl"))
    ap.add_argument("--json-mode", action="store_true")
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--seed", type=int, default=7, help="shuffles row order (temperature is 0)")
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--max-tokens", type=int, default=2000)
    ap.add_argument("--out")
    ap.add_argument("--tag", default="")
    a = ap.parse_args()
    rows_in = load_jsonl(a.data)
    random.Random(a.seed).shuffle(rows_in)
    if a.limit:
        rows_in = rows_in[: a.limit]
    system_prompt = open(a.prompt).read()
    pname = os.path.splitext(os.path.basename(a.prompt))[0] + ("_jsonmode" if a.json_mode else "") + (f"_{a.tag}" if a.tag else "")
    with ThreadPoolExecutor(a.workers) as pool:
        rows = list(pool.map(lambda ex: run_one(a.model, system_prompt, ex, a.json_mode, a.max_tokens), rows_in))
    for r in rows:
        print(("✓" if r["correct"] else ("✗" if r["valid"] else "INVALID")), f"{r['n_correct']}/8 {r['latency']:.2f}s {r['text'][:60]!r}")
    n = len(rows)
    lat = sorted(r["latency"] for r in rows)
    in_tok = sum(r["in_tok"] for r in rows); out_tok = sum(r["out_tok"] for r in rows)
    cost = fw.cost_of(a.model, in_tok, out_tok)
    field_acc = {k: round(sum(r["fields"][k] for r in rows) / n, 4) for k in sc.FIELDS}
    summary = {"model": a.model, "prompt": pname, "json_mode": a.json_mode, "seed": a.seed, "mock": False, "n": n,
               "accuracy": round(sum(r["correct"] for r in rows) / n, 4),
               "mean_field_accuracy": round(sum(r["n_correct"] for r in rows) / (8 * n), 4),
               "field_accuracy": field_acc,
               "invalid_outputs": sum(not r["valid"] for r in rows),
               "p50_latency_s": round(statistics.median(lat), 3), "p95_latency_s": round(lat[int(0.95 * (n - 1))], 3),
               "in_tokens": in_tok, "out_tokens": out_tok, "cost_usd": round(cost, 4),
               "cost_per_1k_requests_usd": round(cost / n * 1000, 4), "rows": rows}
    out = a.out or os.path.join(HERE, "results", f"{a.model.split('/')[-1]}_{pname}_s{a.seed}.json")
    os.makedirs(os.path.dirname(out), exist_ok=True)
    json.dump(summary, open(out, "w"), indent=1)
    print(f"\n{a.model.split('/')[-1]} + {pname}: all-fields {summary['accuracy']:.1%} | field-mean {summary['mean_field_accuracy']:.1%} | invalid {summary['invalid_outputs']} | p50 {summary['p50_latency_s']}s p95 {summary['p95_latency_s']}s | ${summary['cost_per_1k_requests_usd']:.3f}/1k | spend so far ${fw.ledger_total():.3f}")
    print("saved", out)


if __name__ == "__main__":
    main()
