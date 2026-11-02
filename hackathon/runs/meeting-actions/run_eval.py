#!/usr/bin/env python3
"""Run one model + one prompt against data/test.jsonl. Writes results/<model>_<prompt>[_seedN].json
(same top-level shape as hackathon/eval/run_eval.py: accuracy = item F1).

    python3 run_eval.py --model accounts/fireworks/models/glm-5p3-flash --prompt prompts/v1_plain.txt
"""
import argparse, json, os, random, statistics, sys, time
from concurrent.futures import ThreadPoolExecutor, as_completed
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "scripts"))
import fw
import score as S

ROOT = os.path.dirname(os.path.abspath(__file__))
# Per-model request knobs. glm-5p3 is thinking-only: `low` gives 0 reasoning tokens (smoke test, DECISIONS.md).
MODEL_EXTRA = {  # probed 22:25 on one row each; see RESULTS.md gotchas
    "accounts/fireworks/models/glm-5p3": {"reasoning_effort": "low"},        # "none" rejected (thinking-only); low -> 0 reasoning tokens
    "accounts/fireworks/models/glm-5p3-flash": {"reasoning_effort": "low"},
    "accounts/fireworks/models/nemotron-lightning-3p5-30b-a3b": {"reasoning_effort": "none"},  # "low" still burns all 1024 tokens
    "accounts/fireworks/models/deepseek-v4p1-flash": {"reasoning_effort": "none"},             # same
    "accounts/fireworks/models/gpt-oss-120b": {"reasoning_effort": "low"},   # "none" rejected (HTTP 400); low ~170 reasoning tokens
    "accounts/fireworks/models/kimi-k3": {"reasoning_effort": "low"},        # ~50 reasoning tokens; frontier gets its thinking
}


def load_jsonl(p):
    return [json.loads(l) for l in open(p) if l.strip()]


def one(model, system_prompt, ex, max_tokens, extra, json_mode, tag):
    msgs = [{"role": "system", "content": system_prompt}, {"role": "user", "content": "Transcript:\n\n" + ex["text"]}]
    x = dict(extra or {})
    if json_mode:  # plain json_object collapsed the list to ONE object (see RESULTS gotchas); constrain with a schema instead
        x["response_format"] = {"type": "json_object", "schema": {
            "type": "object", "properties": {"action_items": {"type": "array", "items": {
                "type": "object", "properties": {"owner": {"type": "string"}, "task": {"type": "string"}, "due": {"type": ["string", "null"]}},
                "required": ["owner", "task", "due"]}}}, "required": ["action_items"]}}
        msgs[0]["content"] += '\n\nReturn a JSON object of the form {"action_items": [ ... ]}.'
    raw, lat, tin, tout, data = fw.chat(model, msgs, max_tokens=max_tokens, extra=x or None, tag=tag)
    usage = data.get("usage") or {}
    reasoning = (usage.get("completion_tokens_details") or {}).get("reasoning_tokens") or 0
    sc = S.score_rows(ex["items"], raw)
    pred = S.parse_output(raw)
    return {"id": ex["id"], "gold": ex["items"], "raw": raw, "pred": pred, "score": sc, "latency": lat,
            "in_tokens": tin, "out_tokens": tout, "reasoning_tokens": reasoning, "cost": fw.cost_of(model, tin, tout),
            "correct": sc["valid"] and sc["tp"] == sc["n_gold"] == sc["n_pred"] and sc["due_correct"] == sc["due_total"]}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", required=True)
    ap.add_argument("--prompt", required=True)
    ap.add_argument("--data", default=os.path.join(ROOT, "data", "test.jsonl"))
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--seed", type=int, default=0, help="shuffles row order; 0 = natural order")
    ap.add_argument("--max-tokens", type=int, default=1024)
    ap.add_argument("--json-mode", action="store_true")
    ap.add_argument("--workers", type=int, default=6)
    ap.add_argument("--out")
    ap.add_argument("--tag", default="")
    args = ap.parse_args()

    examples = load_jsonl(args.data)
    if args.seed:
        random.Random(args.seed).shuffle(examples)
    if args.limit:
        examples = examples[: args.limit]
    system_prompt = open(args.prompt).read()
    pname = os.path.splitext(os.path.basename(args.prompt))[0] + ("_json" if args.json_mode else "")
    short = fw.SHORT.get(args.model, args.model.split("/")[-1])
    out = args.out or os.path.join(ROOT, "results", f"{short}_{pname}" + (f"_seed{args.seed}" if args.seed else "") + ".json")
    tag = args.tag or f"{short}:{pname}"
    extra = MODEL_EXTRA.get(args.model)

    rows, errors = [], 0
    t_start = time.time()
    with ThreadPoolExecutor(args.workers) as ex:
        futs = {ex.submit(one, args.model, system_prompt, e, args.max_tokens, extra, args.json_mode, tag): e for e in examples}
        for fut in as_completed(futs):
            try:
                rows.append(fut.result())
            except fw.CapReached as e:
                print("CAP REACHED:", e); break
            except Exception as e:
                errors += 1; print("ERR", futs[fut]["id"], str(e)[:200])
    rows.sort(key=lambda r: r["id"])
    if not rows:
        sys.exit("no rows scored")
    agg = S.aggregate([r["score"] for r in rows])
    lats = sorted(r["latency"] for r in rows)
    n = len(rows)
    cost_total = sum(r["cost"] for r in rows)
    summary = {
        "model": args.model, "prompt": pname, "mock": False, "n": n, "seed": args.seed, "errors": errors,
        "accuracy": agg["f1"], "precision": agg["precision"], "recall": agg["recall"], "f1": agg["f1"],
        "due_acc": agg["due_acc"], "exact_row_acc": agg["exact_row_acc"], "invalid_outputs": agg["invalid"],
        "p50_latency_s": round(statistics.median(lats), 3), "p95_latency_s": round(lats[int(0.95 * (n - 1))], 3),
        "cost_per_1k_requests_usd": round(cost_total / n * 1000, 4),
        "avg_in_tokens": round(sum(r["in_tokens"] for r in rows) / n), "avg_out_tokens": round(sum(r["out_tokens"] for r in rows) / n),
        "avg_reasoning_tokens": round(sum(r["reasoning_tokens"] for r in rows) / n),
        "wall_s": round(time.time() - t_start, 1), "rows": rows,
    }
    os.makedirs(os.path.dirname(out), exist_ok=True)
    json.dump(summary, open(out, "w"), indent=1)
    print(f"{short} + {pname} (n={n}): F1 {agg['f1']:.3f} P {agg['precision']:.3f} R {agg['recall']:.3f} due {agg['due_acc']:.3f} "
          f"| invalid {agg['invalid']} | p50 {summary['p50_latency_s']}s p95 {summary['p95_latency_s']}s | ${summary['cost_per_1k_requests_usd']:.3f}/1k "
          f"| reasoning avg {summary['avg_reasoning_tokens']} | ledger ${fw.ledger_total():.3f}")
    print("saved", out)


if __name__ == "__main__":
    main()
