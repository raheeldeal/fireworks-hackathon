#!/usr/bin/env python3
"""
Run one model + one prompt against the eval set. Writes a results JSON.

Mock mode (no API key needed):
    python3 run_eval.py --model small --prompt prompts/v1_plain.txt --mock

Real mode (needs FIREWORKS_API_KEY):
    python3 run_eval.py --model accounts/fireworks/models/llama-v3p1-8b-instruct --prompt prompts/v2_rubric.txt

Standard library only, so nothing to install.
"""
import argparse
import json
import os
import random
import statistics
import sys
import time
import urllib.request

LABELS = ["billing", "bug", "feature_request", "account_access", "how_to"]

# $ per 1M tokens (input, output). Serverless standard rates from docs.fireworks.ai/serverless/pricing, 2026-11-01.
PRICING = {
    "small": (0.20, 0.20),   # mock
    "big": (0.90, 0.90),     # mock
    "finetuned": (0.20, 0.20),  # mock
    "accounts/fireworks/models/nemotron-lightning-3p5-30b-a3b": (0.05, 0.20),
    "accounts/fireworks/models/glm-5p3-flash": (0.15, 0.50),
    "accounts/fireworks/models/gpt-oss-120b": (0.15, 0.60),
    "accounts/fireworks/models/deepseek-v4p1-flash": (0.30, 1.20),
    "accounts/fireworks/models/minimax-m3": (0.30, 1.20),
    "accounts/fireworks/models/glm-5p3": (1.40, 4.40),
    "accounts/fireworks/models/qwen3p8-max": (2.00, 6.00),
    "accounts/fireworks/models/kimi-k3": (3.00, 15.00),
}

# Mock behaviour per model: how often it gets the answer right, and typical latency.
MOCK_PROFILES = {
    "small": {"accuracy": 0.70, "latency": 0.35},
    "big": {"accuracy": 0.90, "latency": 1.10},
    "finetuned": {"accuracy": 0.94, "latency": 0.35},
}
MOCK_PROMPT_BONUS = {"v1_plain": 0.0, "v2_rubric": 0.08}


def load_jsonl(path):
    with open(path) as f:
        return [json.loads(line) for line in f if line.strip()]


def mock_call(model, prompt_name, example, rng):
    """Pretend to be a model. Deterministic given the seed so runs are repeatable."""
    profile = MOCK_PROFILES.get(model, MOCK_PROFILES["small"])
    p_correct = min(0.99, profile["accuracy"] + MOCK_PROMPT_BONUS.get(prompt_name, 0.0))
    time.sleep(0.01)  # keep it fast; latency is simulated below
    latency = rng.gauss(profile["latency"], profile["latency"] * 0.2)
    if rng.random() < p_correct:
        answer = example["label"]
    else:
        answer = rng.choice([l for l in LABELS if l != example["label"]])
    return answer, max(0.05, latency), 60, 4  # answer, seconds, in_tokens, out_tokens


def fireworks_call(model, system_prompt, example):
    key = os.environ.get("FIREWORKS_API_KEY")
    if not key:
        sys.exit("FIREWORKS_API_KEY not set. Use --mock or export your key.")
    body = json.dumps({
        "model": model,
        "max_tokens": 512,  # reasoning models think before answering; too small and you get nothing back
        "temperature": 0,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": example["text"]},
        ],
    }).encode()
    req = urllib.request.Request(
        "https://api.fireworks.ai/inference/v1/chat/completions",
        data=body,
        headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
    )
    t0 = time.time()
    with urllib.request.urlopen(req, timeout=60) as resp:
        data = json.load(resp)
    latency = time.time() - t0
    answer = data["choices"][0]["message"].get("content") or ""
    usage = data.get("usage", {})
    reasoning = (usage.get("completion_tokens_details") or {}).get("reasoning_tokens") or 0
    if reasoning:
        print(f"   (used {reasoning} hidden reasoning tokens)")
    return answer, latency, usage.get("prompt_tokens", 0), usage.get("completion_tokens", 0)


def normalize(answer):
    """Guardrail: turn whatever the model said into one of our labels, or 'invalid'."""
    if not answer:
        return "invalid"
    if "</think>" in answer:  # some models leak their thinking; keep only what comes after
        answer = answer.split("</think>")[-1]
    a = answer.strip().lower().strip(".\"' ").replace(" ", "_").replace("-", "_")
    for label in LABELS:
        if a == label or a.startswith(label):
            return label
    return "invalid"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", required=True)
    ap.add_argument("--prompt", required=True, help="path to a prompt .txt")
    ap.add_argument("--data", default=os.path.join(os.path.dirname(__file__), "data", "tickets.jsonl"))
    ap.add_argument("--mock", action="store_true")
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--seed", type=int, default=7)
    ap.add_argument("--out", help="results json path (default: results/<model>_<prompt>.json)")
    args = ap.parse_args()

    examples = load_jsonl(args.data)
    if args.limit:
        examples = examples[: args.limit]
    system_prompt = open(args.prompt).read()
    prompt_name = os.path.splitext(os.path.basename(args.prompt))[0]
    rng = random.Random(args.seed + sum(map(ord, args.model + prompt_name)))

    rows, latencies, in_tok, out_tok = [], [], 0, 0
    for ex in examples:
        if args.mock:
            raw, lat, ti, to = mock_call(args.model, prompt_name, ex, rng)
        else:
            raw, lat, ti, to = fireworks_call(args.model, system_prompt, ex)
        pred = normalize(raw)
        correct = pred == ex["label"]
        rows.append({"id": ex["id"], "text": ex["text"], "label": ex["label"], "raw": raw, "pred": pred, "correct": correct, "latency": lat})
        latencies.append(lat)
        in_tok += ti
        out_tok += to
        print(("✓" if correct else "✗"), f"{ex['label']:16s} -> {pred:16s} {lat:.2f}s  {ex['text'][:60]}")

    n = len(rows)
    acc = sum(r["correct"] for r in rows) / n
    invalid = sum(r["pred"] == "invalid" for r in rows)
    price_in, price_out = PRICING.get(args.model, (0.0, 0.0))
    cost_total = (in_tok * price_in + out_tok * price_out) / 1_000_000
    cost_per_1k = cost_total / n * 1000
    lat_sorted = sorted(latencies)
    summary = {
        "model": args.model,
        "prompt": prompt_name,
        "mock": args.mock,
        "n": n,
        "accuracy": round(acc, 4),
        "invalid_outputs": invalid,
        "p50_latency_s": round(statistics.median(latencies), 3),
        "p95_latency_s": round(lat_sorted[int(0.95 * (n - 1))], 3),
        "cost_per_1k_requests_usd": round(cost_per_1k, 4),
        "rows": rows,
    }

    out = args.out or os.path.join(os.path.dirname(__file__), "results", f"{args.model.split('/')[-1]}_{prompt_name}.json")
    os.makedirs(os.path.dirname(out), exist_ok=True)
    with open(out, "w") as f:
        json.dump(summary, f, indent=2)

    print(f"\n{args.model} + {prompt_name}: accuracy {acc:.1%} | invalid {invalid} | p50 {summary['p50_latency_s']}s | ${cost_per_1k:.4f} per 1k")
    print(f"saved {out}")


if __name__ == "__main__":
    main()
