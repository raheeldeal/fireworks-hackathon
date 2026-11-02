#!/usr/bin/env python3
"""Run one model + one prompt on data/test.jsonl for the NL -> regex task. Writes results JSON.

Adapted from hackathon/eval/run_eval.py; same JSON shape (model, prompt, n, accuracy, invalid_outputs,
p50/p95 latency, cost_per_1k_requests_usd, rows) plus soft_score and timeouts.

    venv/bin/python run_eval.py --model accounts/fireworks/models/glm-5p3-flash --prompt prompts/v1_plain.txt
    venv/bin/python run_eval.py --model ... --prompt ... --limit 100 --seed 1 --json-mode --logprobs

Every real call is appended to ledger.csv (timestamp, model, in_tokens, out_tokens, cost). The run
refuses to start a paid call once the ledger total reaches --cap (default $3.00).
"""
import argparse
import concurrent.futures as cf
import csv
import json
import math
import os
import random
import statistics
import sys
import time
import urllib.error
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from score import extract_regex, score_row  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
LEDGER = os.path.join(HERE, "ledger.csv")

# $ per 1M tokens (input, output). Serverless standard, verified 2026-11-01 (runs/PROTOCOL.md).
PRICING = {
    "accounts/fireworks/models/nemotron-lightning-3p5-30b-a3b": (0.05, 0.20),
    "accounts/fireworks/models/glm-5p3-flash": (0.15, 0.50),
    "accounts/fireworks/models/gpt-oss-120b": (0.15, 0.60),
    "accounts/fireworks/models/deepseek-v4p1-flash": (0.30, 1.20),
    "accounts/fireworks/models/glm-5p3": (1.40, 4.40),
    "accounts/fireworks/models/kimi-k3": (3.00, 15.00),
}


def load_jsonl(path):
    with open(path) as f:
        return [json.loads(line) for line in f if line.strip()]


def ledger_total():
    if not os.path.exists(LEDGER):
        return 0.0
    with open(LEDGER) as f:
        return sum(float(r["cost"]) for r in csv.DictReader(f))


def ledger_append(model, in_tok, out_tok, cost, note=""):
    new = not os.path.exists(LEDGER)
    with open(LEDGER, "a", newline="") as f:
        w = csv.writer(f)
        if new:
            w.writerow(["timestamp", "model", "in_tokens", "out_tokens", "cost", "note"])
        w.writerow([time.strftime("%Y-%m-%dT%H:%M:%S"), model, in_tok, out_tok, f"{cost:.6f}", note])


def fireworks_call(model, system_prompt, user_text, max_tokens, json_mode=False, logprobs=False, few_shot=None, reasoning_effort=None):
    key = os.environ.get("FIREWORKS_API_KEY")
    if not key:
        sys.exit("FIREWORKS_API_KEY not set (source ~/.zshrc)")
    messages = [{"role": "system", "content": system_prompt}]
    for q, a in (few_shot or []):
        messages.append({"role": "user", "content": q})
        messages.append({"role": "assistant", "content": a})
    messages.append({"role": "user", "content": user_text})
    payload = {"model": model, "max_tokens": max_tokens, "temperature": 0, "messages": messages}
    if json_mode:
        payload["response_format"] = {"type": "json_schema", "json_schema": {"name": "regex", "schema": {
            "type": "object", "properties": {"regex": {"type": "string"}}, "required": ["regex"]}}}
    if logprobs:
        payload["logprobs"] = True
    if reasoning_effort:
        payload["reasoning_effort"] = reasoning_effort
    body = json.dumps(payload).encode()
    req = urllib.request.Request(
        "https://api.fireworks.ai/inference/v1/chat/completions", data=body,
        headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"})
    delay = 2.0
    for attempt in range(9):
        t0 = time.time()
        try:
            with urllib.request.urlopen(req, timeout=120) as resp:
                data = json.load(resp)
            break
        except urllib.error.HTTPError as e:
            code = e.code
            if code in (429, 500, 502, 503, 504) and attempt < 8:
                time.sleep(delay + random.random())
                delay = min(delay * 2, 60)
                continue
            if code == 412:
                raise SystemExit(f"HTTP 412 account suspended / credit depleted; stop: {e.read()[:200]!r}")
            raise RuntimeError(f"HTTP {code}: {e.read()[:300]!r}")
        except (urllib.error.URLError, TimeoutError, OSError) as e:
            if attempt < 8:
                time.sleep(delay + random.random())
                delay = min(delay * 2, 60)
                continue
            raise
    latency = time.time() - t0
    choice = data["choices"][0]
    msg = choice["message"]
    content = msg.get("content") or ""
    usage = data.get("usage", {})
    reasoning_tok = (usage.get("completion_tokens_details") or {}).get("reasoning_tokens") or 0
    conf = None
    if logprobs and choice.get("logprobs") and choice["logprobs"].get("content"):
        lps = [t["logprob"] for t in choice["logprobs"]["content"] if t.get("logprob") is not None]
        if lps:
            conf = round(float(math.exp(sum(lps) / len(lps))), 4)  # geometric-mean token probability
    return {
        "content": content,
        "latency": latency,
        "in_tokens": usage.get("prompt_tokens", 0),
        "out_tokens": usage.get("completion_tokens", 0),
        "reasoning_tokens": reasoning_tok,
        "finish_reason": choice.get("finish_reason"),
        "confidence": conf,
        "had_reasoning_field": bool(msg.get("reasoning_content") or msg.get("reasoning")),
    }


def build_row(ex, r):
    pred = extract_regex(r["content"])
    sc = score_row(pred, ex["positives"], ex["negatives"])
    return sc, {"id": ex["id"], "text": ex["text"], "gold": ex["gold"], "raw": r["content"], "pred": pred,
                "valid": sc["valid"], "correct": sc["correct"], "soft": sc["soft"], "pos_ok": sc["pos_ok"],
                "neg_ok": sc["neg_ok"], "timeouts": sc["timeouts"], "error": sc["error"],
                "latency": round(r["latency"], 3), "in_tokens": r["in_tokens"], "out_tokens": r["out_tokens"],
                "reasoning_tokens": r["reasoning_tokens"], "finish_reason": r["finish_reason"],
                "confidence": r["confidence"]}


def repair(args):
    """Re-query rows whose HTTP request failed after all retries (shared account rate limit), keep everything else."""
    path = args.repair
    summary = json.load(open(path))
    examples = {ex["id"]: ex for ex in load_jsonl(args.data)}
    system_prompt = open(args.prompt).read()
    few_shot = [(r["text"], r["gold"]) for r in load_jsonl(args.few_shot)] if args.few_shot else None
    bad = [i for i, row in enumerate(summary["rows"]) if str(row.get("finish_reason", "")).startswith("error")]
    if not bad:
        print("nothing to repair"); return
    price_in, price_out = PRICING.get(summary["model"], (0.0, 0.0))
    if ledger_total() >= args.cap:
        sys.exit("cap reached")
    in_tok = out_tok = 0
    for i in bad:
        ex = examples[summary["rows"][i]["id"]]
        r = fireworks_call(summary["model"], system_prompt, ex["text"], summary["max_tokens"], summary["json_mode"], args.logprobs, few_shot, summary["reasoning_effort"])
        sc, row = build_row(ex, r)
        summary["rows"][i] = row
        in_tok += r["in_tokens"]; out_tok += r["out_tokens"]
        print(("✓" if sc["correct"] else "✗"), ex["id"], repr(ex["text"][:50]), "->", repr(str(row["pred"])[:40]), row["finish_reason"])
    cost = (in_tok * price_in + out_tok * price_out) / 1e6
    ledger_append(summary["model"], in_tok, out_tok, cost, summary["prompt"] + " repair")
    rows = summary["rows"]; n = len(rows)
    summary["in_tokens"] += in_tok; summary["out_tokens"] += out_tok
    summary["cost_usd"] = round(summary["cost_usd"] + cost, 5)
    summary["cost_per_1k_requests_usd"] = round(summary["cost_usd"] / n * 1000, 4)
    summary["accuracy"] = round(sum(r["correct"] for r in rows) / n, 4)
    summary["soft_score"] = round(sum(r["soft"] for r in rows) / n, 4)
    summary["invalid_outputs"] = sum(not r["valid"] for r in rows)
    summary["timeouts"] = sum(r["timeouts"] for r in rows)
    summary["truncated"] = sum(1 for r in rows if r["finish_reason"] == "length")
    lat = sorted(r["latency"] for r in rows if r["latency"] > 0)
    summary["p50_latency_s"] = round(statistics.median(lat), 3)
    summary["p95_latency_s"] = round(lat[int(0.95 * (len(lat) - 1))], 3)
    summary["repaired_rows"] = summary.get("repaired_rows", 0) + len(bad)
    with open(path, "w") as f:
        json.dump(summary, f, indent=1, ensure_ascii=False)
    print(f"repaired {len(bad)} rows; accuracy now {summary['accuracy']:.1%}; +${cost:.4f}; saved {path}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", required=True)
    ap.add_argument("--prompt", required=True, help="path to a system prompt .txt")
    ap.add_argument("--data", default=os.path.join(HERE, "data", "test.jsonl"))
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--seed", type=int, default=0, help="0 = file order; otherwise shuffle order with this seed")
    ap.add_argument("--max-tokens", type=int, default=512)
    ap.add_argument("--json-mode", action="store_true")
    ap.add_argument("--logprobs", action="store_true")
    ap.add_argument("--few-shot", help="jsonl of rows to prepend as user/assistant turns")
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--reasoning-effort", default=None, help='e.g. "none" (nemotron/deepseek/kimi) or "low" (glm, gpt-oss)')
    ap.add_argument("--cap", type=float, default=3.0)
    ap.add_argument("--tag", default="", help="extra label for the output file / results row")
    ap.add_argument("--out")
    ap.add_argument("--repair", help="existing results .json: re-query only rows whose request errored (e.g. HTTP 429 after retries), rescore, rewrite")
    args = ap.parse_args()
    if args.repair:
        return repair(args)

    examples = load_jsonl(args.data)
    if args.seed:
        random.Random(args.seed).shuffle(examples)
    if args.limit:
        examples = examples[: args.limit]
    system_prompt = open(args.prompt).read()
    prompt_name = os.path.splitext(os.path.basename(args.prompt))[0] + (f"_{args.tag}" if args.tag else "")
    few_shot = None
    if args.few_shot:
        few_shot = [(r["text"], r["gold"]) for r in load_jsonl(args.few_shot)]
    price_in, price_out = PRICING.get(args.model, (0.0, 0.0))
    if args.model not in PRICING:
        print(f"WARNING: no price for {args.model}; cost will be 0", file=sys.stderr)

    spent = ledger_total()
    if spent >= args.cap:
        sys.exit(f"ledger total ${spent:.2f} >= cap ${args.cap:.2f}; refusing to make paid calls")

    def work(ex):
        r = fireworks_call(args.model, system_prompt, ex["text"], args.max_tokens, args.json_mode, args.logprobs, few_shot, args.reasoning_effort)
        return ex, r

    rows, latencies, in_tok, out_tok = [], [], 0, 0
    t_start = time.time()
    with cf.ThreadPoolExecutor(max_workers=args.workers) as pool:
        futs = {pool.submit(work, ex): ex for ex in examples}
        done = 0
        for fut in cf.as_completed(futs):
            ex = futs[fut]
            try:
                ex, r = fut.result()
            except SystemExit as e:
                print(str(e), file=sys.stderr)
                for f2 in futs:
                    f2.cancel()
                sys.exit(f"aborted after {done} rows (nothing saved): account error")
            except Exception as e:
                r = {"content": "", "latency": 0.0, "in_tokens": 0, "out_tokens": 0, "reasoning_tokens": 0,
                     "finish_reason": f"error: {e}", "confidence": None, "had_reasoning_field": False}
            sc, row = build_row(ex, r)
            rows.append(row)
            latencies.append(r["latency"])
            in_tok += r["in_tokens"]
            out_tok += r["out_tokens"]
            done += 1
            cost_so_far = (in_tok * price_in + out_tok * price_out) / 1e6
            print(("✓" if sc["correct"] else ("✗" if sc["valid"] else "!")), f"{done:3d}/{len(examples)} {r['latency']:5.2f}s "
                  f"soft={sc['soft']:.2f} {ex['text'][:50]!r} -> {str(row['pred'])[:40]!r}", flush=True)
            if spent + cost_so_far >= args.cap:
                print(f"CAP REACHED (${spent + cost_so_far:.2f}); cancelling remaining calls", file=sys.stderr)
                for f2 in futs:
                    f2.cancel()
                break
    wall = time.time() - t_start

    # keep rows in test-file order for diffing
    order = {ex["id"]: i for i, ex in enumerate(examples)}
    rows.sort(key=lambda r: order[r["id"]])
    n = len(rows)
    cost_total = (in_tok * price_in + out_tok * price_out) / 1e6
    ledger_append(args.model, in_tok, out_tok, cost_total, prompt_name)
    acc = sum(r["correct"] for r in rows) / n
    invalid = sum(not r["valid"] for r in rows)
    lat_sorted = sorted(latencies)
    summary = {
        "model": args.model,
        "prompt": prompt_name,
        "mock": False,
        "n": n,
        "accuracy": round(acc, 4),
        "soft_score": round(sum(r["soft"] for r in rows) / n, 4),
        "invalid_outputs": invalid,
        "timeouts": sum(r["timeouts"] for r in rows),
        "truncated": sum(1 for r in rows if r["finish_reason"] == "length"),
        "p50_latency_s": round(statistics.median(latencies), 3),
        "p95_latency_s": round(lat_sorted[int(0.95 * (n - 1))], 3),
        "cost_per_1k_requests_usd": round(cost_total / n * 1000, 4),
        "in_tokens": in_tok, "out_tokens": out_tok, "cost_usd": round(cost_total, 5),
        "seed": args.seed, "max_tokens": args.max_tokens, "json_mode": args.json_mode, "reasoning_effort": args.reasoning_effort, "wall_s": round(wall, 1),
        "rows": rows,
    }
    out = args.out or os.path.join(HERE, "results", f"{args.model.split('/')[-1]}_{prompt_name}" + (f"_seed{args.seed}" if args.seed else "") + ".json")
    os.makedirs(os.path.dirname(out), exist_ok=True)
    with open(out, "w") as f:
        json.dump(summary, f, indent=1, ensure_ascii=False)
    print(f"\n{args.model} + {prompt_name}: accuracy {acc:.1%} | soft {summary['soft_score']:.3f} | invalid {invalid} | "
          f"truncated {summary['truncated']} | p50 {summary['p50_latency_s']}s | p95 {summary['p95_latency_s']}s | "
          f"${summary['cost_per_1k_requests_usd']:.4f}/1k | run cost ${cost_total:.4f} | ledger ${ledger_total():.4f}")
    print(f"saved {out}")


if __name__ == "__main__":
    main()
