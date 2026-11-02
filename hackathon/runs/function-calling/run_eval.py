#!/usr/bin/env python3
"""Run one model x one configuration on the function-calling test set. Writes results/<name>.json.

Modes:
  --mode tools : native `tools` parameter; the call is read from message.tool_calls (fallback: parse content)
  --mode json  : plain prompt; tools are rendered as JSON in the system prompt; the call is parsed from content

Examples:
  python3 run_eval.py --model accounts/fireworks/models/nemotron-lightning-3p5-30b-a3b --mode tools --prompt prompts/v1_plain.txt
  python3 run_eval.py --model accounts/fireworks/models/kimi-k3 --mode tools --prompt prompts/v1_plain.txt --limit 100
  python3 run_eval.py --model ... --mode json --prompt prompts/v2_rubric.txt --shots 5 --response-format json_schema
Adapted from hackathon/eval/run_eval.py (same output shape, plus partial score / confidence / token fields).
"""
import argparse, csv, json, os, random, statistics, sys, time, threading, re
import urllib.request, urllib.error
from concurrent.futures import ThreadPoolExecutor
from score import score, parse_call, norm_name

ENDPOINT = "https://api.fireworks.ai/inference/v1/chat/completions"
HERE = os.path.dirname(os.path.abspath(__file__))
SPEND_CAP = 3.00  # PROTOCOL.md rule 2

# $ per 1M tokens (input, output). PROTOCOL.md, verified 2026-11-01.
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
        return [json.loads(l) for l in f if l.strip()]

def ledger_total(path):
    if not os.path.exists(path):
        return 0.0
    with open(path) as f:
        return sum(float(r["cost"]) for r in csv.DictReader(f))

def ledger_append(path, model, in_tok, out_tok, cost, note):
    new = not os.path.exists(path)
    with open(path, "a", newline="") as f:
        w = csv.writer(f)
        if new:
            w.writerow(["timestamp", "model", "in_tokens", "out_tokens", "cost", "note"])
        w.writerow([time.strftime("%Y-%m-%dT%H:%M:%S"), model, in_tok, out_tok, f"{cost:.6f}", note])

_SAFE = re.compile(r"[^a-zA-Z0-9_-]")
def sanitize_tools(tools):
    """Tool-API names must match [a-zA-Z0-9_-]{1,64}; BFCL names have dots. Return (tools, reverse map)."""
    out, rev = [], {}
    for t in tools:
        name = t["function"]["name"]
        safe = _SAFE.sub("_", name)[:64]
        rev[safe] = name
        f = dict(t["function"]); f["name"] = safe
        out.append({"type": "function", "function": f})
    return out, rev

def render_tools_text(tools):
    return json.dumps([t["function"] for t in tools], ensure_ascii=False)

def few_shot_text(shots):
    parts = []
    for s in shots:
        user = [m for m in s["messages"] if m["role"] == "user"][-1]["content"]
        parts.append(f"Tools: {render_tools_text(s['tools'])}\nRequest: {user}\nCall: {json.dumps(s['answer'], ensure_ascii=False)}")
    return "\n\n".join(parts)

def build_request(args, system_prompt, shots, ex):
    sys_text = system_prompt
    if shots:
        sys_text += "\n\nExamples:\n\n" + few_shot_text(shots)
    body = {"model": args.model, "temperature": 0, "max_tokens": args.max_tokens}
    if args.logprobs:
        body["logprobs"] = True
    if args.reasoning_effort:
        body["reasoning_effort"] = args.reasoning_effort
    rev = {}
    if args.mode == "tools":
        tools, rev = sanitize_tools(ex["tools"])
        body["tools"] = tools
        if args.tool_choice != "auto":
            body["tool_choice"] = args.tool_choice
        messages = [{"role": "system", "content": sys_text}]
    else:
        messages = [{"role": "system", "content": sys_text + "\n\nAvailable tools (JSON):\n" + render_tools_text(ex["tools"])}]
        if args.response_format == "json_object":
            body["response_format"] = {"type": "json_object"}
        elif args.response_format == "json_schema":
            body["response_format"] = {"type": "json_schema", "json_schema": {"name": "tool_call", "schema": {
                "type": "object", "properties": {"name": {"type": "string"}, "arguments": {"type": "object"}},
                "required": ["name", "arguments"]}}}
    for m in ex["messages"]:
        if m["role"] == "system":   # a few BFCL rows carry their own system message; keep it after ours
            messages.append({"role": "system", "content": m["content"]})
        else:
            messages.append({"role": "user", "content": m["content"]})
    body["messages"] = messages
    return body, rev

def call_api(body, timeout=180):
    key = os.environ.get("FIREWORKS_API_KEY") or sys.exit("FIREWORKS_API_KEY not set")
    data = json.dumps(body).encode()
    last = None
    for attempt in range(6):
        req = urllib.request.Request(ENDPOINT, data=data, headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"})
        t0 = time.time()
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return json.load(resp), time.time() - t0
        except urllib.error.HTTPError as e:
            txt = e.read().decode(errors="ignore")[:300]
            last = f"HTTP {e.code}: {txt}"
            if e.code in (429, 500, 502, 503, 504, 408) and attempt < 5:
                time.sleep(min(60, 2 ** attempt * 2 + random.random()))
                continue
            return {"error": last}, time.time() - t0
        except Exception as e:  # timeouts, connection resets
            last = f"{type(e).__name__}: {e}"
            if attempt < 5:
                time.sleep(min(60, 2 ** attempt * 2))
                continue
            return {"error": last}, time.time() - t0
    return {"error": last}, 0.0

def extract(args, data, rev):
    """Return (pred call or None, raw text, source, confidence)."""
    if "error" in data:
        return None, data["error"], "error", None
    choice = data["choices"][0]
    msg = choice["message"]
    content = msg.get("content") or ""
    pred, source = None, "none"
    tcs = msg.get("tool_calls") or []
    if tcs:
        f = tcs[0].get("function") or {}
        a = f.get("arguments")
        if isinstance(a, str):
            try: a = json.loads(a)
            except Exception: a = a
        name = f.get("name", "")
        pred = {"name": rev.get(name, name), "arguments": a if a is not None else {}}
        source = "tool_calls"
    if pred is None and content:
        pred = parse_call(content)
        if pred:
            source = "content"
            pred["name"] = rev.get(pred["name"], pred["name"])
    conf = None
    lp = choice.get("logprobs")
    if lp and lp.get("content"):
        toks = lp["content"]
        usage = data.get("usage", {})
        reasoning = (usage.get("completion_tokens_details") or {}).get("reasoning_tokens") or 0
        comp = usage.get("completion_tokens") or len(toks)
        n_answer = max(1, comp - reasoning)
        answer_toks = toks[-n_answer:] if len(toks) >= n_answer else toks
        vals = [t["logprob"] for t in answer_toks if t.get("logprob") is not None]
        if vals:
            conf = round(sum(vals) / len(vals), 4)   # mean token logprob of the answer part
    raw = (content or "")[:400] if content else json.dumps(tcs)[:400]
    return pred, raw, source, conf

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", required=True)
    ap.add_argument("--mode", choices=["tools", "json"], default="tools")
    ap.add_argument("--prompt", default=os.path.join(HERE, "prompts", "v1_plain.txt"))
    ap.add_argument("--data", default=os.path.join(HERE, "data", "test.jsonl"))
    ap.add_argument("--shots", type=int, default=0, help="few-shot examples from data/train.jsonl rendered into the system prompt")
    ap.add_argument("--tool-choice", default="auto", choices=["auto", "required"])
    ap.add_argument("--response-format", default="none", choices=["none", "json_object", "json_schema"])
    ap.add_argument("--logprobs", action="store_true", help="record mean answer-token logprob as confidence")
    ap.add_argument("--max-tokens", type=int, default=1024)
    ap.add_argument("--reasoning-effort", default="", help="e.g. low: glm-5p3 accepts it and cuts hidden reasoning (sibling finding)")
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--seed", type=int, default=0, help="0 = file order; otherwise shuffle order with this seed")
    ap.add_argument("--concurrency", type=int, default=4)
    ap.add_argument("--name", help="results file stem (default derived)")
    ap.add_argument("--out")
    ap.add_argument("--ledger", default=os.path.join(HERE, "ledger.csv"))
    ap.add_argument("--price-in", type=float, help="override $/M input (for models not in the table)")
    ap.add_argument("--price-out", type=float)
    args = ap.parse_args()

    spent = ledger_total(args.ledger)
    if spent >= SPEND_CAP:
        sys.exit(f"SPEND CAP REACHED: ledger total ${spent:.2f} >= ${SPEND_CAP:.2f}. Not running.")

    examples = load_jsonl(args.data)
    if args.seed:
        random.Random(args.seed).shuffle(examples)
    if args.limit:
        examples = examples[: args.limit]
    system_prompt = open(args.prompt).read().strip()
    prompt_name = os.path.splitext(os.path.basename(args.prompt))[0]
    shots = []
    if args.shots:
        train = load_jsonl(os.path.join(HERE, "data", "train.jsonl"))
        train = [t for t in train if len(json.dumps(t["tools"])) < 1500]   # short examples keep the prompt cheap
        shots = random.Random(42).sample(train, args.shots)
    if "/" not in args.model:
        args.model = "accounts/fireworks/models/" + args.model
    if args.price_in is not None:
        price = (args.price_in, args.price_out)
    elif args.model in PRICING:
        price = PRICING[args.model]
    else:
        sys.exit(f"no price for {args.model}; pass --price-in/--price-out (ledger must never record $0 for a paid run)")
    short = args.model.split("/")[-1]
    stem = args.name or f"{short}_{args.mode}_{prompt_name}" + (f"_shots{args.shots}" if args.shots else "") + \
        (f"_{args.tool_choice}" if args.tool_choice != "auto" else "") + (f"_{args.response_format}" if args.response_format != "none" else "") + \
        (f"_seed{args.seed}" if args.seed else "") + (f"_re{args.reasoning_effort}" if args.reasoning_effort else "")
    out = args.out or os.path.join(HERE, "results", stem + ".json")

    lock = threading.Lock()
    tot = {"in": 0, "out": 0, "reason": 0, "cost": 0.0, "done": 0}
    stop = threading.Event()

    def work(ex):
        if stop.is_set():
            return {"id": ex["id"], "source": ex["source"], "gold": ex["answer"], "pred": None, "strict": 0, "partial": 0,
                    "invalid": True, "reason": "skipped: spend cap", "latency": 0, "in_tokens": 0, "out_tokens": 0, "reasoning_tokens": 0,
                    "confidence": None, "raw": "", "pred_source": "skipped"}
        body, rev = build_request(args, system_prompt, shots, ex)
        data, lat = call_api(body)
        pred, raw, src, conf = extract(args, data, rev)
        s = score(pred, ex["acceptable"])
        usage = data.get("usage", {}) or {}
        ti, to = usage.get("prompt_tokens", 0) or 0, usage.get("completion_tokens", 0) or 0
        rt = (usage.get("completion_tokens_details") or {}).get("reasoning_tokens") or 0
        cost = (ti * price[0] + to * price[1]) / 1e6
        with lock:
            tot["in"] += ti; tot["out"] += to; tot["reason"] += rt; tot["cost"] += cost; tot["done"] += 1
            if spent + tot["cost"] >= SPEND_CAP:
                stop.set()
            mark = "✓" if s["strict"] else ("~" if s["partial"] else "✗")
            print(f"{mark} {tot['done']:3d}/{len(examples)} {ex['id']:28s} {lat:5.1f}s rt={rt:4d} {s['reason'][:70]}", flush=True)
        return {"id": ex["id"], "source": ex["source"], "gold": ex["answer"], "pred": pred, "strict": s["strict"], "partial": s["partial"],
                "invalid": s["invalid"], "name_ok": s["name_ok"], "reason": s["reason"], "latency": round(lat, 3), "in_tokens": ti, "out_tokens": to,
                "reasoning_tokens": rt, "confidence": conf, "raw": raw, "pred_source": src}

    t_start = time.time()
    try:
        with ThreadPoolExecutor(max_workers=args.concurrency) as pool:
            rows = list(pool.map(work, examples))
    finally:
        ledger_append(args.ledger, args.model, tot["in"], tot["out"], tot["cost"], stem)

    n = len(rows)
    lats = sorted(r["latency"] for r in rows if r["pred_source"] != "skipped") or [0]
    acc = sum(r["strict"] for r in rows) / n
    acc_p = sum(r["partial"] for r in rows) / n
    invalid = sum(1 for r in rows if r["invalid"])
    errors = sum(1 for r in rows if r["pred_source"] == "error")
    by_src = {}
    for r in rows:
        b = by_src.setdefault(r["source"].replace("BFCL_v4_", "").replace(".json", ""), [0, 0])
        b[0] += r["strict"]; b[1] += 1
    summary = {
        "model": args.model, "prompt": prompt_name, "mode": args.mode, "shots": args.shots, "tool_choice": args.tool_choice,
        "response_format": args.response_format, "seed": args.seed, "mock": False, "n": n,
        "accuracy": round(acc, 4), "accuracy_partial": round(acc_p, 4), "invalid_outputs": invalid, "api_errors": errors,
        "p50_latency_s": round(statistics.median(lats), 3), "p95_latency_s": round(lats[int(0.95 * (len(lats) - 1))], 3),
        "cost_per_1k_requests_usd": round(tot["cost"] / n * 1000, 4), "total_cost_usd": round(tot["cost"], 5),
        "in_tokens": tot["in"], "out_tokens": tot["out"], "reasoning_tokens": tot["reason"],
        "accuracy_by_source": {k: round(v[0] / v[1], 3) for k, v in by_src.items()},
        "wall_s": round(time.time() - t_start, 1), "capped": stop.is_set(), "rows": rows,
    }
    os.makedirs(os.path.dirname(out), exist_ok=True)
    with open(out, "w") as f:
        json.dump(summary, f, indent=1, ensure_ascii=False)
    print(f"\n{stem}: strict {acc:.1%} | partial {acc_p:.1%} | invalid {invalid} | errors {errors} | p50 {summary['p50_latency_s']}s p95 {summary['p95_latency_s']}s | ${summary['cost_per_1k_requests_usd']:.3f}/1k | run cost ${tot['cost']:.4f} | by source {summary['accuracy_by_source']}")
    print(f"ledger total now ${spent + tot['cost']:.4f}; saved {out}")

if __name__ == "__main__":
    main()
