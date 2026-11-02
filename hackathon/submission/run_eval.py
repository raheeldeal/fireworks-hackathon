#!/usr/bin/env python3
"""Run one model + one prompt on the test set. Adapted from hackathon/eval/run_eval.py; keeps the JSON shape.

  python3 run_eval.py --model nemotron-lightning-3p5-30b-a3b --prompt prompts/v1_plain.txt
Options: --retrieve K (keyword top-K catalog instead of full), --reasoning low|none|high, --json (json_object mode),
         --shots N (N train examples appended to the system prompt), --seed S (shuffles row order), --logprobs,
         --limit N, --workers W, --out path, --tag name
"""
import argparse, json, os, random, statistics, sys, time, concurrent.futures as cf
import fw, score as sc
from retrieve import Retriever
HERE = os.path.dirname(os.path.abspath(__file__))

def load_jsonl(p):
    return [json.loads(l) for l in open(p) if l.strip()]

def catalog_text(tools):
    return "\n".join(f"{t['name']}: {t['description']}" for t in tools)

def build_system(template, tools, shots):
    s = template.replace("{CATALOG}", catalog_text(tools))
    if shots:
        s += "\n\nEXAMPLES:\n" + "\n".join(f"Request: {x['text']}\nTool: {x['label']}" for x in shots)
    return s

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", required=True)
    ap.add_argument("--prompt", required=True)
    ap.add_argument("--data", default=os.path.join(HERE, "data", "test.jsonl"))
    ap.add_argument("--retrieve", type=int, default=0)
    ap.add_argument("--reasoning", default=None)
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--shots", type=int, default=0)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--logprobs", action="store_true")
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--max_tokens", type=int, default=1024)
    ap.add_argument("--out")
    ap.add_argument("--tag", default="")
    args = ap.parse_args()

    rows_in = load_jsonl(args.data)
    if args.seed:
        random.Random(args.seed).shuffle(rows_in)
    if args.limit:
        rows_in = rows_in[: args.limit]
    template = open(args.prompt).read()
    prompt_name = os.path.splitext(os.path.basename(args.prompt))[0]
    catalog = json.load(open(os.path.join(HERE, "data", "catalog.json")))
    shots = []
    if args.shots:
        train = load_jsonl(os.path.join(HERE, "data", "train.jsonl"))
        shots = random.Random(42).sample(train, args.shots)
    retr = Retriever(catalog) if args.retrieve else None
    extra = {}
    if args.reasoning: extra["reasoning_effort"] = args.reasoning
    if args.json: extra["response_format"] = {"type": "json_object"}
    if args.logprobs: extra.update({"logprobs": True, "top_logprobs": 5})
    config = f"{prompt_name}" + (f"+retr{args.retrieve}" if args.retrieve else "") + (f"+r{args.reasoning}" if args.reasoning else "") + ("+json" if args.json else "") + (f"+{args.shots}shot" if args.shots else "")
    tag = args.tag or config
    model_short = args.model.split("/")[-1]
    note = f"{model_short}:{tag}:s{args.seed}"

    def one(ex):
        tools = retr.top(ex["text"], args.retrieve) if retr else catalog
        sys_p = build_system(template, tools, shots)
        msgs = [{"role": "system", "content": sys_p}, {"role": "user", "content": ex["text"]}]
        try:
            r = fw.chat(args.model, msgs, max_tokens=args.max_tokens, extra=extra or None, note=note)
        except fw.CapReached as e:
            raise
        except Exception as e:
            r = {"content": "", "reasoning": "", "latency": 0.0, "in_tokens": 0, "out_tokens": 0, "reasoning_tokens": 0, "finish_reason": f"error: {str(e)[:120]}", "raw": {}}
        s = sc.score(r["content"], ex["label"])
        row = {"id": ex["id"], "text": ex["text"], "label": ex["label"], "raw": r["content"], "pred": s["pred"], "ranked": s["ranked"],
               "correct": s["top1"], "top3": s["top3"], "latency": round(r["latency"], 3), "in_tokens": r["in_tokens"],
               "out_tokens": r["out_tokens"], "reasoning_tokens": r["reasoning_tokens"], "finish_reason": r["finish_reason"]}
        if retr:
            row["retrieved"] = [t["name"] for t in tools]
            row["retrieval_hit"] = ex["label"] in row["retrieved"]
        if args.logprobs:
            try:
                lp = r["raw"]["choices"][0]["logprobs"]["content"]
                toks = [t for t in lp if t.get("token", "").strip()]
                row["first_token_logprob"] = toks[0]["logprob"] if toks else None
                row["sum_logprob"] = sum(t["logprob"] for t in lp)
            except Exception:
                row["first_token_logprob"] = None; row["sum_logprob"] = None
        return row

    rows = []
    with cf.ThreadPoolExecutor(args.workers) as ex:
        futs = [ex.submit(one, e) for e in rows_in]
        for f in futs:
            try:
                row = f.result()
            except fw.CapReached as e:
                print("CAP REACHED:", e); break
            rows.append(row)
            print(("✓" if row["correct"] else "✗"), f"{row['label']:28s} -> {row['pred']:28s} {row['latency']:.2f}s  {row['text'][:50]}")

    n = len(rows)
    if not n: sys.exit("no rows")
    n_err = sum(str(r["finish_reason"]).startswith("error") for r in rows)
    if n_err > n / 2:
        sys.exit(f"{n_err}/{n} calls errored (first: {next(r['finish_reason'] for r in rows if str(r['finish_reason']).startswith('error'))}); not saving")
    lat = sorted(r["latency"] for r in rows)
    tin = sum(r["in_tokens"] for r in rows); tout = sum(r["out_tokens"] for r in rows); trs = sum(r["reasoning_tokens"] for r in rows)
    pi, po = fw.PRICING.get(fw.model_id(args.model), (0, 0))
    cost_total = (tin * pi + tout * po) / 1e6
    # catalog share of cost: catalog chars / total prompt chars, scaled to measured input tokens
    sample = rows_in[:50]
    def prompt_chars(ex):
        tools = retr.top(ex["text"], args.retrieve) if retr else catalog
        return len(catalog_text(tools)), len(build_system(template, tools, shots)) + len(ex["text"])
    cc = [prompt_chars(e) for e in sample]
    cat_frac = sum(a for a, b in cc) / sum(b for a, b in cc)
    cat_tokens_est = cat_frac * tin / n
    cat_cost = cat_tokens_est * n * pi / 1e6
    summary = {
        "model": fw.model_id(args.model), "prompt": config, "tag": tag, "mock": False, "n": n, "seed": args.seed,
        "accuracy": round(sum(r["correct"] for r in rows) / n, 4),
        "top3_accuracy": round(sum(r["top3"] for r in rows) / n, 4),
        "invalid_outputs": sum(r["pred"] == "invalid" for r in rows),
        "errors": sum(str(r["finish_reason"]).startswith("error") for r in rows),
        "p50_latency_s": round(statistics.median(lat), 3), "p95_latency_s": round(lat[int(0.95 * (n - 1))], 3),
        "cost_per_1k_requests_usd": round(cost_total / n * 1000, 4),
        "in_tokens": tin, "out_tokens": tout, "reasoning_tokens": trs,
        "avg_in_tokens": round(tin / n, 1), "avg_out_tokens": round(tout / n, 1),
        "catalog_tokens_est": round(cat_tokens_est), "catalog_cost_share": round(cat_cost / cost_total, 3) if cost_total else None,
        "retrieval_recall": round(sum(r.get("retrieval_hit", False) for r in rows) / n, 4) if retr else None,
        "rows": rows,
    }
    out = args.out or os.path.join(HERE, "results", f"{model_short}__{tag}__s{args.seed}.json")
    os.makedirs(os.path.dirname(out), exist_ok=True)
    json.dump(summary, open(out, "w"), indent=1)
    print(f"\n{model_short} + {tag}: acc {summary['accuracy']:.1%} top3 {summary['top3_accuracy']:.1%} | invalid {summary['invalid_outputs']} | p50 {summary['p50_latency_s']}s p95 {summary['p95_latency_s']}s | ${summary['cost_per_1k_requests_usd']:.4f}/1k | catalog share {summary['catalog_cost_share']} | ledger ${fw.ledger_total():.3f}")
    print("saved", out)

if __name__ == "__main__":
    main()
