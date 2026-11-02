#!/usr/bin/env python3
"""Run one model + one prompt over data/test.jsonl against Fireworks. Adapted from hackathon/eval/run_eval.py.
Adds: label-list templating, few-shot, JSON mode, logprob confidence, retries with backoff, a cost ledger with a
hard cap, concurrency, macro-F1. Output JSON keeps the shared harness shape plus extra fields.

  python3 run_eval.py --model accounts/fireworks/models/nemotron-lightning-3p5-30b-a3b --prompt prompts/v1_plain.txt
"""
import argparse, csv, json, os, random, statistics, sys, threading, time, urllib.request, urllib.error
from concurrent.futures import ThreadPoolExecutor
import score

HERE = os.path.dirname(os.path.abspath(__file__))
LEDGER = os.path.join(HERE, "ledger.csv")
CAP_USD = 3.00
PRICING = {  # $ per 1M tokens (input, output); PROTOCOL.md table, verified 2026-11-01
    "accounts/fireworks/models/nemotron-lightning-3p5-30b-a3b": (0.05, 0.20),
    "accounts/fireworks/models/glm-5p3-flash": (0.15, 0.50),
    "accounts/fireworks/models/gpt-oss-120b": (0.15, 0.60),
    "accounts/fireworks/models/deepseek-v4p1-flash": (0.30, 1.20),
    "accounts/fireworks/models/glm-5p3": (1.40, 4.40),
    "accounts/fireworks/models/kimi-k3": (3.00, 15.00),
}
_lock = threading.Lock()

def load_jsonl(p):
    return [json.loads(l) for l in open(p) if l.strip()]

def ledger_total():
    if not os.path.exists(LEDGER):
        return 0.0
    with open(LEDGER) as f:
        return sum(float(r["cost"]) for r in csv.DictReader(f))

def ledger_add(model, ti, to, note=""):
    pi, po = PRICING.get(model, (0.0, 0.0))
    cost = (ti * pi + to * po) / 1e6
    with _lock:
        new = not os.path.exists(LEDGER)
        with open(LEDGER, "a", newline="") as f:
            w = csv.writer(f)
            if new:
                w.writerow(["timestamp", "model", "in_tokens", "out_tokens", "cost", "note"])
            w.writerow([time.strftime("%Y-%m-%dT%H:%M:%S"), model, ti, to, f"{cost:.6f}", note])
    return cost

def build_system(prompt_path, fewshot_k, seed):
    labels = json.load(open(os.path.join(HERE, "data", "labels.json")))["labels"]
    label_block = "\n".join(f"- {l['name']}: {l['definition']}" for l in labels)
    tmpl = open(prompt_path).read()
    examples = ""
    if fewshot_k:
        train = load_jsonl(os.path.join(HERE, "data", "train.jsonl"))
        rng = random.Random(1000 + seed)
        rng.shuffle(train)
        # pick k examples from distinct labels, favouring the confusable families
        picked, seen = [], set()
        for r in train:
            if r["label"] not in seen:
                picked.append(r); seen.add(r["label"])
            if len(picked) == fewshot_k:
                break
        examples = "\n\n".join(f"Clause: {r['text']}\nCategory: {r['label']}" for r in picked)
    return tmpl.replace("{LABELS}", label_block).replace("{EXAMPLES}", examples)

def call(model, system, text, max_tokens, json_mode, logprobs, reasoning_effort, no_think=False):
    key = os.environ.get("FIREWORKS_API_KEY") or sys.exit("FIREWORKS_API_KEY not set")
    body = {"model": model, "max_tokens": max_tokens, "temperature": 0,
            "messages": [{"role": "system", "content": system}, {"role": "user", "content": text}]}
    if json_mode:
        body["response_format"] = {"type": "json_object"}
    if logprobs:
        body["logprobs"] = True
        body["top_logprobs"] = 5
    if no_think:
        body["chat_template_kwargs"] = {"enable_thinking": False}
    if reasoning_effort:
        body["reasoning_effort"] = reasoning_effort
    req = urllib.request.Request("https://api.fireworks.ai/inference/v1/chat/completions", data=json.dumps(body).encode(),
                                 headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"})
    delay = 2.0
    for attempt in range(9):
        t0 = time.time()
        try:
            with urllib.request.urlopen(req, timeout=120) as resp:
                data = json.load(resp)
            lat = time.time() - t0
            ch = data["choices"][0]
            msg = ch["message"]
            content = msg.get("content") or ""
            usage = data.get("usage", {}) or {}
            conf = None
            lp = ch.get("logprobs")
            if lp and lp.get("content"):
                # confidence = probability of the first generated content token
                import math
                conf = round(math.exp(lp["content"][0]["logprob"]), 4)
            return {"raw": content, "latency": lat, "in": usage.get("prompt_tokens", 0), "out": usage.get("completion_tokens", 0),
                    "reasoning_tokens": (usage.get("completion_tokens_details") or {}).get("reasoning_tokens") or 0,
                    "finish": ch.get("finish_reason"), "confidence": conf,
                    "reasoning_len": len(msg.get("reasoning_content") or msg.get("reasoning") or "")}
        except urllib.error.HTTPError as e:
            body_txt = e.read().decode(errors="replace")[:300]
            if e.code == 400 and no_think and any(k in body_txt.lower() for k in ("chat_template", "enable_thinking", "thinking", "reasoning")):
                # model's template has no thinking switch: fall back to reasoning_effort low
                print(f"   {model.split('/')[-1]} rejected enable_thinking, falling back to reasoning_effort=low", file=sys.stderr)
                body.pop("chat_template_kwargs", None); no_think = False
                body["reasoning_effort"] = reasoning_effort = reasoning_effort or "low"
                req = urllib.request.Request(req.full_url, data=json.dumps(body).encode(), headers=req.headers)
                continue
            if e.code == 400 and reasoning_effort and "reasoning" in body_txt.lower():
                # model does not accept reasoning_effort: drop it and retry once
                print(f"   {model.split('/')[-1]} rejected reasoning_effort, retrying without it", file=sys.stderr)
                body.pop("reasoning_effort", None); reasoning_effort = None
                req = urllib.request.Request(req.full_url, data=json.dumps(body).encode(), headers=req.headers)
                continue
            if e.code in (429, 500, 502, 503, 504) and attempt < 8:
                print(f"   HTTP {e.code} on {model.split('/')[-1]}, retry in {delay:.0f}s: {body_txt[:80]}", file=sys.stderr)
                time.sleep(delay); delay = min(delay * 2, 30)
                continue
            return {"raw": "", "latency": time.time() - t0, "in": 0, "out": 0, "reasoning_tokens": 0, "finish": f"error {e.code}: {body_txt}", "confidence": None, "reasoning_len": 0}
        except Exception as e:  # timeouts, connection resets
            if attempt < 8:
                print(f"   {type(e).__name__} on {model.split('/')[-1]}, retry in {delay:.0f}s", file=sys.stderr)
                time.sleep(delay); delay = min(delay * 2, 30)
                continue
            return {"raw": "", "latency": time.time() - t0, "in": 0, "out": 0, "reasoning_tokens": 0, "finish": f"error {e}", "confidence": None, "reasoning_len": 0}

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", required=True)
    ap.add_argument("--prompt", required=True)
    ap.add_argument("--data", default=os.path.join(HERE, "data", "test.jsonl"))
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--seed", type=int, default=7, help="shuffles row order and few-shot choice")
    ap.add_argument("--fewshot", type=int, default=0)
    ap.add_argument("--json-mode", action="store_true")
    ap.add_argument("--logprobs", action="store_true")
    ap.add_argument("--reasoning-effort", default=None)
    ap.add_argument("--no-think", action="store_true", help="chat_template_kwargs.enable_thinking=false (falls back to reasoning_effort=low)")
    ap.add_argument("--max-tokens", type=int, default=512)
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--tag", default="", help="suffix for the output file name")
    ap.add_argument("--out")
    args = ap.parse_args()

    rows_in = load_jsonl(args.data)
    rng = random.Random(args.seed)
    rng.shuffle(rows_in)
    if args.limit:
        rows_in = rows_in[: args.limit]
    system = build_system(args.prompt, args.fewshot, args.seed)
    prompt_name = os.path.splitext(os.path.basename(args.prompt))[0]
    name = f"{args.model.split('/')[-1]}_{prompt_name}{('_' + args.tag) if args.tag else ''}_s{args.seed}"
    out = args.out or os.path.join(HERE, "results", name + ".json")
    # guard against two drivers launching the same run: an atomic lock dir per output file
    lock = out + ".lock"
    if os.path.exists(out):
        sys.exit(f"{out} exists; skipping")
    try:
        os.mkdir(lock)
    except FileExistsError:
        sys.exit(f"{lock} held by another process; skipping")
    stopped = {"cap": False}

    def one(ex):
        if ledger_total() >= CAP_USD:
            stopped["cap"] = True
            return None
        r = call(args.model, system, ex["text"], args.max_tokens, args.json_mode, args.logprobs, args.reasoning_effort, args.no_think)
        ledger_add(args.model, r["in"], r["out"], name)
        pred = score.normalize(r["raw"])
        row = {"id": ex["id"], "text": ex["text"], "label": ex["label"], "raw": r["raw"][:2000], "pred": pred,
               "correct": pred == ex["label"], "latency": round(r["latency"], 3), "in_tokens": r["in"], "out_tokens": r["out"],
               "reasoning_tokens": r["reasoning_tokens"], "finish": r["finish"], "confidence": r["confidence"]}
        print(("✓" if row["correct"] else "✗"), f"{ex['label']:28s} -> {pred:28s} {r['latency']:.2f}s out={r['out']} {ex['text'][:50]!r}", flush=True)
        return row

    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        rows = [r for r in pool.map(one, rows_in) if r is not None]
    if not rows:
        sys.exit("no rows scored (cap reached?)")
    m = score.metrics(rows)
    lat = sorted(r["latency"] for r in rows)
    ti, to = sum(r["in_tokens"] for r in rows), sum(r["out_tokens"] for r in rows)
    pi, po = PRICING.get(args.model, (0, 0))
    cost = (ti * pi + to * po) / 1e6
    summary = {"model": args.model, "prompt": prompt_name, "tag": args.tag, "seed": args.seed, "fewshot": args.fewshot,
               "json_mode": args.json_mode, "no_think": args.no_think, "reasoning_effort": args.reasoning_effort, "max_tokens": args.max_tokens, "prompt_path": args.prompt, "mock": False, "n": m["n"], "accuracy": m["accuracy"], "macro_f1": m["macro_f1"],
               "invalid_outputs": m["invalid"], "p50_latency_s": round(statistics.median(lat), 3),
               "p95_latency_s": round(lat[int(0.95 * (len(lat) - 1))], 3), "in_tokens": ti, "out_tokens": to,
               "cost_usd": round(cost, 4), "cost_per_1k_requests_usd": round(cost / m["n"] * 1000, 4),
               "stopped_at_cap": stopped["cap"], "rows": rows}
    os.makedirs(os.path.dirname(out), exist_ok=True)
    json.dump(summary, open(out, "w"), indent=1)
    os.rmdir(lock)
    print(f"\n{name}: acc {m['accuracy']:.1%} | macroF1 {m['macro_f1']:.3f} | invalid {m['invalid']} | p50 {summary['p50_latency_s']}s p95 {summary['p95_latency_s']}s | ${summary['cost_per_1k_requests_usd']:.3f}/1k | run cost ${cost:.3f} | ledger ${ledger_total():.3f}")
    print(f"saved {out}")

if __name__ == "__main__":
    main()
