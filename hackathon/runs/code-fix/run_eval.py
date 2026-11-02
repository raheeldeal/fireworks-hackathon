#!/usr/bin/env python3
"""Run one model + one prompt over data/test.jsonl, score each answer by executing hidden tests, write results JSON.

Adapted from hackathon/eval/run_eval.py (same output shape, plus per-row `status`). Adds:
  * ledger.csv spend tracking with a hard cap (protocol rule 2)
  * retries with exponential backoff on 429/5xx (rule 7), concurrency (default 4 threads)
  * reasoning-model handling: content may be None; `reasoning_tokens` are logged (rule 6)
  * --shots N: few-shot messages pulled from data/train.jsonl (never from test)
  * --json: Fireworks JSON mode (response_format json_object with a schema hint)
  * --seed: shuffles example order (variance runs)
  * --confidence: appends a "Confidence: NN" line request to the system prompt, parsed into row["confidence"]

Example:
  python3 run_eval.py --model accounts/fireworks/models/glm-5p3-flash --prompt prompts/v1_plain.txt
"""
import argparse, csv, json, os, random, re, statistics, sys, threading, time, urllib.error, urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed

from score import score

HERE = os.path.dirname(os.path.abspath(__file__))
LEDGER = os.path.join(HERE, "ledger.csv")
SPEND_CAP = 3.00
ENDPOINT = "https://api.fireworks.ai/inference/v1/chat/completions"

# $ per 1M tokens (input, output). From hackathon/runs/PROTOCOL.md, verified 2026-11-01.
PRICING = {
    "accounts/fireworks/models/nemotron-lightning-3p5-30b-a3b": (0.05, 0.20),
    "accounts/fireworks/models/glm-5p3-flash": (0.15, 0.50),
    "accounts/fireworks/models/gpt-oss-120b": (0.15, 0.60),
    "accounts/fireworks/models/deepseek-v4p1-flash": (0.30, 1.20),
    "accounts/fireworks/models/glm-5p3": (1.40, 4.40),
    "accounts/fireworks/models/kimi-k3": (3.00, 15.00),
}
SHORT = {m: m.split("/")[-1] for m in PRICING}

_ledger_lock = threading.Lock()


def ledger_total():
    if not os.path.exists(LEDGER):
        return 0.0
    with open(LEDGER) as f:
        return sum(float(r["cost"]) for r in csv.DictReader(f))


def ledger_add(model, in_tok, out_tok, note=""):
    pin, pout = PRICING.get(model, (0.0, 0.0))
    cost = (in_tok * pin + out_tok * pout) / 1e6
    with _ledger_lock:
        new = not os.path.exists(LEDGER)
        with open(LEDGER, "a", newline="") as f:
            w = csv.writer(f)
            if new:
                w.writerow(["timestamp", "model", "in_tokens", "out_tokens", "cost", "note"])
            w.writerow([time.strftime("%Y-%m-%dT%H:%M:%S"), model, in_tok, out_tok, f"{cost:.6f}", note])
    return cost


class SpendCap(Exception):
    pass


def load_jsonl(path):
    with open(path) as f:
        return [json.loads(l) for l in f if l.strip()]


def fireworks_call(model, messages, max_tokens, json_mode=False, extra=None, timeout=180):
    key = os.environ.get("FIREWORKS_API_KEY")
    if not key:
        sys.exit("FIREWORKS_API_KEY not set (source ~/.zshrc)")
    body = {"model": model, "max_tokens": max_tokens, "temperature": 0, "messages": messages}
    if json_mode:
        body["response_format"] = {"type": "json_object", "schema": {"type": "object", "properties": {"fixed_code": {"type": "string"}}, "required": ["fixed_code"]}}
    if extra:
        body.update(extra)
    data = json.dumps(body).encode()
    delay = 2.0
    for attempt in range(6):
        req = urllib.request.Request(ENDPOINT, data=data, headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"})
        t0 = time.time()
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                out = json.load(resp)
            latency = time.time() - t0
            break
        except urllib.error.HTTPError as e:
            txt = e.read().decode(errors="replace")[:300]
            if e.code in (429, 500, 502, 503, 504) and attempt < 5:
                print(f"   [{SHORT.get(model, model)}] HTTP {e.code}, retry in {delay:.0f}s: {txt[:80]}", file=sys.stderr)
                time.sleep(delay); delay *= 2
                continue
            raise RuntimeError(f"HTTP {e.code}: {txt}")
        except (urllib.error.URLError, TimeoutError, OSError) as e:
            if attempt < 5:
                print(f"   [{SHORT.get(model, model)}] {type(e).__name__}, retry in {delay:.0f}s", file=sys.stderr)
                time.sleep(delay); delay *= 2
                continue
            raise
    msg = out["choices"][0]["message"]
    content = msg.get("content") or ""
    usage = out.get("usage", {}) or {}
    reasoning = (usage.get("completion_tokens_details") or {}).get("reasoning_tokens") or 0
    finish = out["choices"][0].get("finish_reason")
    return content, latency, usage.get("prompt_tokens", 0), usage.get("completion_tokens", 0), reasoning, finish, msg.get("reasoning_content") or msg.get("reasoning")


def build_messages(system_prompt, shots, example):
    msgs = [{"role": "system", "content": system_prompt}]
    for s in shots:
        msgs.append({"role": "user", "content": s["text"]})
        msgs.append({"role": "assistant", "content": "```python\n" + s["reference"].rstrip() + "\n```"})
    msgs.append({"role": "user", "content": example["text"]})
    return msgs


def pick_shots(n, seed=0):
    if n <= 0:
        return []
    train = load_jsonl(os.path.join(HERE, "data", "train.jsonl"))
    # deterministic: shortest-first among a seeded shuffle, so shots stay under budget
    rng = random.Random(seed)
    rng.shuffle(train)
    short = sorted(train[:60], key=lambda r: len(r["text"]) + len(r["reference"]))
    return short[:n]


CONF_RE = re.compile(r"confidence\s*[:=]\s*(\d{1,3})", re.I)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", required=True)
    ap.add_argument("--prompt", required=True)
    ap.add_argument("--data", default=os.path.join(HERE, "data", "test.jsonl"))
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--seed", type=int, default=0, help="0 = original order; otherwise shuffle")
    ap.add_argument("--max-tokens", type=int, default=2048)
    ap.add_argument("--shots", type=int, default=0)
    ap.add_argument("--json", action="store_true", help="Fireworks JSON mode")
    ap.add_argument("--confidence", action="store_true")
    ap.add_argument("--extra", default="", help='extra JSON merged into the request body, e.g. {"reasoning_effort":"low"}')
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--tag", default="", help="suffix for the results filename")
    ap.add_argument("--out")
    args = ap.parse_args()

    examples = load_jsonl(args.data)
    if args.seed:
        random.Random(args.seed).shuffle(examples)
    if args.limit:
        examples = examples[: args.limit]
    system_prompt = open(args.prompt).read().strip()
    if args.confidence:
        system_prompt += "\n\nAfter the code block, add one final line: `Confidence: NN` where NN is 0-100, your probability that the fixed function passes all hidden tests."
    prompt_name = os.path.splitext(os.path.basename(args.prompt))[0]
    cfg = prompt_name + (f"_{args.shots}shot" if args.shots else "") + ("_json" if args.json else "") + ("_conf" if args.confidence else "") + (f"_{args.tag}" if args.tag else "")
    shots = pick_shots(args.shots)
    extra = json.loads(args.extra) if args.extra else None

    spent = ledger_total()
    print(f"ledger so far: ${spent:.4f} (cap ${SPEND_CAP:.2f}); running {len(examples)} rows on {SHORT.get(args.model, args.model)} / {cfg}")

    def work(ex):
        if ledger_total() >= SPEND_CAP:
            raise SpendCap()
        msgs = build_messages(system_prompt, shots, ex)
        try:
            raw, lat, ti, to, rt, finish, _ = fireworks_call(args.model, msgs, args.max_tokens, args.json, extra)
            err = ""
        except Exception as e:  # keep the run alive; count as invalid, no tokens charged
            raw, lat, ti, to, rt, finish, err = "", 0.0, 0, 0, 0, "error", str(e)[:200]
        cost = ledger_add(args.model, ti, to, f"{cfg}:{ex['id']}")
        sc = score(raw, ex)
        conf = None
        if args.confidence:
            m = CONF_RE.findall(raw)
            conf = int(m[-1]) if m else None
        return {"id": ex["id"], "bug_type": ex.get("bug_type"), "text": ex["text"], "raw": raw, "status": sc["status"],
                "correct": bool(sc["correct"]), "invalid": bool(sc["invalid"]), "detail": sc["detail"][:300],
                "latency": lat, "in_tokens": ti, "out_tokens": to, "reasoning_tokens": rt, "finish_reason": finish,
                "confidence": conf, "api_error": err, "cost": cost}

    rows = []
    stopped = False
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        futs = {pool.submit(work, ex): ex for ex in examples}
        for fut in as_completed(futs):
            try:
                r = fut.result()
            except SpendCap:
                stopped = True
                continue
            rows.append(r)
            flag = "✓" if r["correct"] else ("!" if r["invalid"] else "✗")
            print(f"{flag} {r['id']:11s} {r['status']:12s} {r['latency']:5.1f}s out={r['out_tokens']:5d} rt={r['reasoning_tokens']:5d} {r['detail'][:50]!r}")
    if stopped:
        print("SPEND CAP REACHED: run truncated", file=sys.stderr)
    order = {ex["id"]: i for i, ex in enumerate(examples)}
    rows.sort(key=lambda r: order[r["id"]])

    n = len(rows)
    if not n:
        sys.exit("no rows completed")
    lats = sorted(r["latency"] for r in rows if r["latency"] > 0) or [0.0]
    in_tok = sum(r["in_tokens"] for r in rows); out_tok = sum(r["out_tokens"] for r in rows)
    pin, pout = PRICING.get(args.model, (0.0, 0.0))
    cost_total = (in_tok * pin + out_tok * pout) / 1e6
    summary = {
        "model": args.model, "prompt": cfg, "mock": False, "n": n, "seed": args.seed, "shots": args.shots,
        "accuracy": round(sum(r["correct"] for r in rows) / n, 4),
        "invalid_outputs": sum(r["invalid"] for r in rows),
        "api_errors": sum(1 for r in rows if r["api_error"]),
        "truncated_by_cap": stopped,
        "p50_latency_s": round(statistics.median(lats), 3),
        "p95_latency_s": round(lats[int(0.95 * (len(lats) - 1))], 3),
        "cost_per_1k_requests_usd": round(cost_total / n * 1000, 4),
        "avg_in_tokens": round(in_tok / n, 1), "avg_out_tokens": round(out_tok / n, 1),
        "avg_reasoning_tokens": round(sum(r["reasoning_tokens"] for r in rows) / n, 1),
        "run_cost_usd": round(cost_total, 4),
        "rows": rows,
    }
    out = args.out or os.path.join(HERE, "results", f"{SHORT.get(args.model, args.model.split('/')[-1])}_{cfg}" + (f"_seed{args.seed}" if args.seed else "") + (f"_n{args.limit}" if args.limit else "") + ".json")
    os.makedirs(os.path.dirname(out), exist_ok=True)
    with open(out, "w") as f:
        json.dump(summary, f, indent=2)
    print(f"\n{SHORT.get(args.model, args.model)} + {cfg}: accuracy {summary['accuracy']:.1%} | invalid {summary['invalid_outputs']} | p50 {summary['p50_latency_s']}s p95 {summary['p95_latency_s']}s | ${summary['cost_per_1k_requests_usd']:.3f}/1k | run cost ${cost_total:.4f} | ledger ${ledger_total():.4f}")
    print(f"saved {out}")


if __name__ == "__main__":
    main()
