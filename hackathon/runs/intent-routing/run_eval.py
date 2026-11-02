#!/usr/bin/env python3
"""Run one Fireworks model + one prompt on the locked test set. Adapted from hackathon/eval/run_eval.py.
Keeps the same JSON output shape, adds: per-row confidence, retries w/ backoff, thread pool, ledger.csv, spend cap.

  python3 run_eval.py --model accounts/fireworks/models/glm-5p3-flash --prompt prompts/v1_plain.txt
  options: --limit N  --seed S (shuffles row order)  --json-mode  --workers 4  --max-tokens 1024  --out path
"""
import argparse, csv, json, os, random, statistics, sys, threading, time, urllib.error, urllib.request
from concurrent.futures import ThreadPoolExecutor
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from score import parse, canon, LABELS

HERE = os.path.dirname(os.path.abspath(__file__))
SPEND_CAP = 3.00
# $ per 1M tokens (input, output), serverless standard, verified 2026-11-01 (runs/PROTOCOL.md)
PRICING = {
    "accounts/fireworks/models/nemotron-lightning-3p5-30b-a3b": (0.05, 0.20),
    "accounts/fireworks/models/glm-5p3-flash": (0.15, 0.50),
    "accounts/fireworks/models/gpt-oss-120b": (0.15, 0.60),
    "accounts/fireworks/models/deepseek-v4p1-flash": (0.30, 1.20),
    "accounts/fireworks/models/glm-5p3": (1.40, 4.40),
    "accounts/fireworks/models/kimi-k3": (3.00, 15.00),
}
LEDGER = os.path.join(HERE, "ledger.csv")
_lock = threading.Lock()

def ledger_total():
    if not os.path.exists(LEDGER):
        return 0.0
    with open(LEDGER) as f:
        return sum(float(r["cost"]) for r in csv.DictReader(f))

def ledger_add(model, ti, to, tag):
    pi, po = PRICING.get(model, (0.0, 0.0))
    cost = (ti * pi + to * po) / 1e6
    with _lock:
        new = not os.path.exists(LEDGER)
        with open(LEDGER, "a", newline="") as f:
            w = csv.writer(f)
            if new:
                w.writerow(["timestamp", "model", "in_tokens", "out_tokens", "cost", "tag"])
            w.writerow([time.strftime("%Y-%m-%dT%H:%M:%S"), model, ti, to, f"{cost:.6f}", tag])
    return cost

def load_jsonl(p):
    return [json.loads(l) for l in open(p) if l.strip()]

JSON_SCHEMA = {
    "type": "object",
    "properties": {"intent": {"type": "string", "enum": LABELS}, "confidence": {"type": "number"}},
    "required": ["intent", "confidence"],
}

def fireworks_call(model, system_prompt, text, max_tokens, json_mode, tag, effort=None):
    key = os.environ.get("FIREWORKS_API_KEY") or sys.exit("FIREWORKS_API_KEY not set")
    payload = {
        "model": model, "max_tokens": max_tokens, "temperature": 0,
        "messages": [{"role": "system", "content": system_prompt}, {"role": "user", "content": text}],
    }
    if effort:
        payload["reasoning_effort"] = effort
    if json_mode:
        payload["response_format"] = {"type": "json_object", "schema": JSON_SCHEMA}
    body = json.dumps(payload).encode()
    delay = 2.0
    for attempt in range(6):
        if ledger_total() >= SPEND_CAP:
            raise RuntimeError("SPEND CAP REACHED")
        req = urllib.request.Request("https://api.fireworks.ai/inference/v1/chat/completions", data=body,
                                     headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"})
        t0 = time.time()
        try:
            with urllib.request.urlopen(req, timeout=120) as resp:
                data = json.load(resp)
            lat = time.time() - t0
            msg = data["choices"][0]["message"]
            content = msg.get("content") or ""
            usage = data.get("usage", {}) or {}
            ti, to = usage.get("prompt_tokens", 0), usage.get("completion_tokens", 0)
            reasoning = (usage.get("completion_tokens_details") or {}).get("reasoning_tokens") or 0
            ledger_add(model, ti, to, tag)
            return content, lat, ti, to, reasoning, data["choices"][0].get("finish_reason")
        except urllib.error.HTTPError as e:
            if e.code in (429, 500, 502, 503, 504) and attempt < 5:
                time.sleep(delay + random.random()); delay *= 2; continue
            raise
        except (urllib.error.URLError, TimeoutError, ConnectionError) as e:
            if attempt < 5:
                time.sleep(delay + random.random()); delay *= 2; continue
            raise
    raise RuntimeError("retries exhausted")

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", required=True)
    ap.add_argument("--prompt", required=True)
    ap.add_argument("--data", default=os.path.join(HERE, "data", "test.jsonl"))
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--seed", type=int, default=0, help="0 = locked order; otherwise shuffle order with this seed")
    ap.add_argument("--json-mode", action="store_true")
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--max-tokens", type=int, default=4096)
    ap.add_argument("--effort", default=None, help="reasoning_effort: none|low|medium|high (model default if unset)")
    ap.add_argument("--out")
    ap.add_argument("--tag", default="")
    ap.add_argument("--retry-errors", help="path of an existing results json: re-run only rows with error, merge, overwrite")
    args = ap.parse_args()

    examples = load_jsonl(args.data)
    if args.limit:
        examples = examples[: args.limit]
    if args.seed:
        random.Random(args.seed).shuffle(examples)
    system_prompt = open(args.prompt).read()
    pname = os.path.splitext(os.path.basename(args.prompt))[0] + ("_json" if args.json_mode else "") + (f"_{args.effort}" if args.effort else "")
    short = args.model.split("/")[-1]
    tag = args.tag or f"{short}_{pname}" + (f"_s{args.seed}" if args.seed else "") + (f"_n{args.limit}" if args.limit else "")

    def work(ex):
        try:
            raw, lat, ti, to, rs, fin = fireworks_call(args.model, system_prompt, ex["text"], args.max_tokens, args.json_mode, tag, args.effort)
            err = None
        except Exception as e:  # record and keep going; a failed call is an invalid output
            raw, lat, ti, to, rs, fin, err = "", 0.0, 0, 0, 0, None, f"{type(e).__name__}: {e}"[:200]
            if "SPEND CAP" in str(e):
                raise
        pred, conf = parse(raw)
        correct = pred != "invalid" and canon(pred) == canon(ex["label"])
        print(("✓" if correct else "✗"), f"{ex['label'][:28]:28s} -> {pred[:28]:28s} conf={conf} {lat:.2f}s" + (f" ERR {err}" if err else ""), flush=True)
        return {"id": ex["id"], "text": ex["text"], "label": ex["label"], "raw": raw, "pred": pred, "confidence": conf,
                "correct": correct, "latency": lat, "in_tokens": ti, "out_tokens": to, "reasoning_tokens": rs,
                "finish_reason": fin, "error": err}

    prev = None
    if args.retry_errors:
        prev = json.load(open(args.retry_errors))
        bad_ids = {r["id"] for r in prev["rows"] if r["error"]}
        examples = [ex for ex in examples if ex["id"] in bad_ids]
        print(f"retrying {len(examples)} errored rows from {args.retry_errors}")
    with ThreadPoolExecutor(args.workers) as pool:
        rows = list(pool.map(work, examples))
    if prev:
        fixed = {r["id"]: r for r in rows}
        rows = [fixed.get(r["id"], r) for r in prev["rows"]]

    n = len(rows)
    lats = sorted(r["latency"] for r in rows if r["latency"] > 0) or [0.0]
    in_tok, out_tok = sum(r["in_tokens"] for r in rows), sum(r["out_tokens"] for r in rows)
    pi, po = PRICING.get(args.model, (0.0, 0.0))
    cost_total = (in_tok * pi + out_tok * po) / 1e6
    summary = {
        "model": args.model, "prompt": pname, "mock": False, "n": n, "seed": args.seed, "json_mode": args.json_mode, "effort": args.effort, "max_tokens": args.max_tokens,
        "accuracy": round(sum(r["correct"] for r in rows) / n, 4),
        "invalid_outputs": sum(r["pred"] == "invalid" for r in rows),
        "errors": sum(1 for r in rows if r["error"]),
        "p50_latency_s": round(statistics.median(lats), 3),
        "p95_latency_s": round(lats[int(0.95 * (len(lats) - 1))], 3),
        "cost_per_1k_requests_usd": round(cost_total / n * 1000, 4),
        "cost_total_usd": round(cost_total, 4), "in_tokens": in_tok, "out_tokens": out_tok,
        "reasoning_tokens": sum(r["reasoning_tokens"] for r in rows),
        "rows": rows,
    }
    out = args.retry_errors or args.out or os.path.join(HERE, "results", f"{tag}.json")
    os.makedirs(os.path.dirname(out), exist_ok=True)
    json.dump(summary, open(out, "w"), indent=2)
    print(f"\n{short} + {pname}: acc {summary['accuracy']:.1%} | invalid {summary['invalid_outputs']} | err {summary['errors']} | "
          f"p50 {summary['p50_latency_s']}s p95 {summary['p95_latency_s']}s | ${summary['cost_per_1k_requests_usd']:.4f}/1k | run cost ${cost_total:.4f} | ledger ${ledger_total():.4f}")
    print(f"saved {out}")

if __name__ == "__main__":
    main()
