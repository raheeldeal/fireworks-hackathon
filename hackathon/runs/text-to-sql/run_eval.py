#!/usr/bin/env python3
"""Text-to-SQL eval: one model + one prompt against data/test.jsonl. Adapted from hackathon/eval/run_eval.py.
Keeps the same JSON output shape, adds execution scoring, a cost ledger, retries, and concurrency.

    python3 run_eval.py --model accounts/fireworks/models/glm-5p3-flash --prompt prompts/v1_plain.txt
"""
import argparse, concurrent.futures as cf, csv, json, os, random, statistics, sys, time, urllib.request, urllib.error, datetime
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from score import score, extract_sql

HERE = os.path.dirname(os.path.abspath(__file__))
DB_ROOT = os.path.join(HERE, "raw", "zip", "spider_data", "database")
LEDGER = os.path.join(HERE, "ledger.csv")
CAP_USD = 3.00

# $ per 1M tokens (input, output). PROTOCOL.md table, verified 2026-11-01.
PRICING = {
    "accounts/fireworks/models/nemotron-lightning-3p5-30b-a3b": (0.05, 0.20),
    "accounts/fireworks/models/glm-5p3-flash": (0.15, 0.50),
    "accounts/fireworks/models/gpt-oss-120b": (0.15, 0.60),
    "accounts/fireworks/models/deepseek-v4p1-flash": (0.30, 1.20),
    "accounts/fireworks/models/glm-5p3": (1.40, 4.40),
    "accounts/fireworks/models/kimi-k3": (3.00, 15.00),
}

def load_jsonl(p):
    return [json.loads(l) for l in open(p) if l.strip()]

def ledger_total():
    if not os.path.exists(LEDGER):
        return 0.0
    return sum(float(r["cost"]) for r in csv.DictReader(open(LEDGER)))

def ledger_add(model, ti, to, cost, note=""):
    new = not os.path.exists(LEDGER)
    with open(LEDGER, "a", newline="") as f:
        w = csv.writer(f)
        if new:
            w.writerow(["timestamp", "model", "in_tokens", "out_tokens", "cost", "note"])
        w.writerow([datetime.datetime.now().isoformat(timespec="seconds"), model, ti, to, f"{cost:.6f}", note])

def user_message(ex):
    return f"Schema:\n{ex['schema']}\n\nQuestion: {ex['question']}\nSQL:"

def fireworks_call(model, system_prompt, ex, max_tokens, extra):
    key = os.environ.get("FIREWORKS_API_KEY")
    if not key:
        sys.exit("FIREWORKS_API_KEY not set")
    body = {"model": model, "max_tokens": max_tokens, "temperature": 0,
            "messages": [{"role": "system", "content": system_prompt}, {"role": "user", "content": user_message(ex)}]}
    body.update(extra)
    req = urllib.request.Request("https://api.fireworks.ai/inference/v1/chat/completions", data=json.dumps(body).encode(),
                                 headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"})
    last = None
    for attempt in range(6):
        t0 = time.time()
        try:
            with urllib.request.urlopen(req, timeout=120) as resp:
                data = json.load(resp)
            lat = time.time() - t0
            msg = data["choices"][0]["message"]
            content = msg.get("content") or ""
            if not content and msg.get("reasoning_content"):
                content = msg["reasoning_content"]  # thinking model ran out of budget: salvage anything that looks like SQL
            usage = data.get("usage", {})
            reasoning = (usage.get("completion_tokens_details") or {}).get("reasoning_tokens") or 0
            lp = None
            try:
                toks = data["choices"][0].get("logprobs", {}).get("content") or []
                if toks:
                    lp = sum(t["logprob"] for t in toks) / len(toks)
            except Exception:
                lp = None
            return content, lat, usage.get("prompt_tokens", 0), usage.get("completion_tokens", 0), reasoning, lp, None
        except urllib.error.HTTPError as e:
            last = f"HTTP {e.code}: {e.read()[:200]!r}"
            if e.code in (429, 500, 502, 503, 504, 412):
                time.sleep(min(60, 2 ** attempt + random.random()))
                continue
            return "", 0.0, 0, 0, 0, None, last
        except Exception as e:
            last = str(e)[:200]
            time.sleep(min(60, 2 ** attempt))
    return "", 0.0, 0, 0, 0, None, last

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", required=True)
    ap.add_argument("--prompt", required=True)
    ap.add_argument("--data", default=os.path.join(HERE, "data", "test.jsonl"))
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--seed", type=int, default=0, help="shuffles request order (temperature stays 0)")
    ap.add_argument("--max-tokens", type=int, default=1024)
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--extra", default="{}", help="extra JSON merged into the request body (e.g. reasoning_effort, response_format)")
    ap.add_argument("--tag", default="", help="suffix for the results filename")
    ap.add_argument("--out")
    args = ap.parse_args()

    if ledger_total() >= CAP_USD:
        sys.exit(f"ledger total ${ledger_total():.2f} >= cap ${CAP_USD}; refusing to spend more")
    examples = load_jsonl(args.data)
    if args.limit:
        examples = examples[: args.limit]
    order = list(range(len(examples)))
    if args.seed:
        random.Random(args.seed).shuffle(order)
    system_prompt = open(args.prompt).read().strip()
    prompt_name = os.path.splitext(os.path.basename(args.prompt))[0] + (f"_{args.tag}" if args.tag else "")
    extra = json.loads(args.extra)
    price_in, price_out = PRICING.get(args.model, (0.0, 0.0))

    def work(i):
        ex = examples[i]
        raw, lat, ti, to, reasoning, lp, err = fireworks_call(args.model, system_prompt, ex, args.max_tokens, extra)
        db = os.path.join(DB_ROOT, ex["db_id"], ex["db_id"] + ".sqlite")
        s = score(raw, ex["gold_sql"], db)
        return i, {"id": ex["id"], "db_id": ex["db_id"], "question": ex["question"], "gold_sql": ex["gold_sql"], "raw": raw,
                   "pred_sql": s["pred_sql"], "correct": s["exec_match"], "exact": s["exact_match"], "invalid": s["invalid"],
                   "error": s["error"] or err, "latency": lat, "in_tokens": ti, "out_tokens": to, "reasoning_tokens": reasoning,
                   "mean_logprob": lp, "api_error": err}

    rows = [None] * len(examples)
    in_tok = out_tok = 0
    with cf.ThreadPoolExecutor(args.workers) as pool:
        for i, r in pool.map(work, order):
            rows[i] = r
            in_tok += r["in_tokens"]; out_tok += r["out_tokens"]
            print(("✓" if r["correct"] else ("!" if r["invalid"] else "✗")), f"{r['db_id']:28s} {r['latency']:.2f}s  {r['question'][:60]}", flush=True)
    cost_total = (in_tok * price_in + out_tok * price_out) / 1e6
    ledger_add(args.model, in_tok, out_tok, cost_total, f"{prompt_name} n={len(rows)} seed={args.seed}")

    n = len(rows)
    lats = sorted(r["latency"] for r in rows)
    api_errors = sum(1 for r in rows if r["api_error"])
    summary = {
        "model": args.model, "prompt": prompt_name, "mock": False, "n": n, "seed": args.seed,
        "accuracy": round(sum(r["correct"] for r in rows) / n, 4),
        "exact_match": round(sum(r["exact"] for r in rows) / n, 4),
        "invalid_outputs": sum(r["invalid"] for r in rows), "api_errors": api_errors,
        "p50_latency_s": round(statistics.median(lats), 3), "p95_latency_s": round(lats[int(0.95 * (n - 1))], 3),
        "in_tokens": in_tok, "out_tokens": out_tok, "reasoning_tokens": sum(r["reasoning_tokens"] for r in rows),
        "cost_total_usd": round(cost_total, 5), "cost_per_1k_requests_usd": round(cost_total / n * 1000, 4),
        "extra": extra, "rows": rows,
    }
    out = args.out or os.path.join(HERE, "results", f"{args.model.split('/')[-1]}_{prompt_name}" + (f"_seed{args.seed}" if args.seed else "") + ".json")
    os.makedirs(os.path.dirname(out), exist_ok=True)
    json.dump(summary, open(out, "w"), indent=1)
    print(f"\n{args.model} + {prompt_name}: exec acc {summary['accuracy']:.1%} | exact {summary['exact_match']:.1%} | invalid {summary['invalid_outputs']} | api_err {api_errors} | p50 {summary['p50_latency_s']}s p95 {summary['p95_latency_s']}s | ${summary['cost_per_1k_requests_usd']:.3f}/1k | run ${cost_total:.4f} | ledger ${ledger_total():.3f}")
    print("saved", out)

if __name__ == "__main__":
    main()
