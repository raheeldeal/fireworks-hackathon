#!/usr/bin/env python3
"""Run one model + one prompt against the locked test set. Writes a results JSON with the
same shape as hackathon/eval/run_eval.py (accuracy = mean per-note set F1; exact_accuracy added).

  python3 run_eval.py --model accounts/fireworks/models/glm-5p3-flash --prompt prompts/v1_plain.txt
"""
import argparse, json, os, random, statistics, sys, time
from concurrent.futures import ThreadPoolExecutor
import fw, score

HERE = os.path.dirname(os.path.abspath(__file__))
CODES = json.load(open(os.path.join(HERE, "data", "codes.json")))["codes"]
CODE_LIST = "\n".join(f"{c}: {d}" for c, d in CODES)


def load_jsonl(p):
    return [json.loads(l) for l in open(p) if l.strip()]


def build_system(prompt_path, shots_path=None, n_shots=5, seed=7):
    sp = open(prompt_path).read().replace("{CODE_LIST}", CODE_LIST)
    if "{SHOTS}" in sp:
        rows = load_jsonl(shots_path)
        rng = random.Random(seed)
        shots = rng.sample(rows, n_shots)
        txt = "\n\n".join(f"Note:\n{r['text']}\nCodes: {json.dumps(r['codes'])}" for r in shots)
        sp = sp.replace("{SHOTS}", txt)
    return sp


def run_one(model, system_prompt, ex, max_tokens, extra, tag):
    msgs = [{"role": "system", "content": system_prompt}, {"role": "user", "content": "Note:\n" + ex["text"]}]
    try:
        r = fw.chat(model, msgs, max_tokens=max_tokens, temperature=0, tag=tag, extra=extra)
    except fw.CapReached as e:
        raise
    except Exception as e:
        print("ERROR", ex["id"], e, file=sys.stderr)
        r = {"content": "", "reasoning_tokens": 0, "in_tokens": 0, "out_tokens": 0, "latency": 0.0, "finish_reason": "error", "cost": 0.0}
    s = score.score(r["content"], ex["codes"])
    row = {"id": ex["id"], "text": ex["text"], "label": ex["codes"], "raw": r["content"], "pred": s["pred"],
           "correct": s["exact"], "f1": s["f1"], "invalid": s["invalid"], "latency": round(r["latency"], 3),
           "in_tokens": r["in_tokens"], "out_tokens": r["out_tokens"], "reasoning_tokens": r["reasoning_tokens"],
           "finish_reason": r["finish_reason"], "cost": r["cost"]}
    # optional confidence for routing: {"codes": [...], "confidence": 0.8}
    try:
        obj = json.loads(r["content"].strip().strip("`").replace("json\n", "", 1))
        if isinstance(obj, dict) and "confidence" in obj:
            row["confidence"] = float(obj["confidence"])
    except Exception:
        pass
    mark = "✓" if s["exact"] else ("~" if s["f1"] > 0 else "✗")
    print(f"{mark} {ex['id']} gold={ex['codes']} pred={s['pred']} f1={s['f1']:.2f} {r['latency']:.1f}s rt={r['reasoning_tokens']}", flush=True)
    return row


def summarize(model, prompt_name, rows, extra_meta=None):
    n = len(rows)
    lat = sorted(r["latency"] for r in rows)
    tin = sum(r["in_tokens"] for r in rows)
    tout = sum(r["out_tokens"] for r in rows)
    cost_total = sum(r["cost"] for r in rows)
    summary = {
        "model": model, "prompt": prompt_name, "mock": False, "n": n,
        "accuracy": round(sum(r["f1"] for r in rows) / n, 4),          # mean set-F1 (primary metric)
        "exact_accuracy": round(sum(r["correct"] for r in rows) / n, 4),
        "invalid_outputs": sum(r["invalid"] for r in rows),
        "p50_latency_s": round(statistics.median(lat), 3),
        "p95_latency_s": round(lat[int(0.95 * (n - 1))], 3),
        "cost_per_1k_requests_usd": round(cost_total / n * 1000, 4),
        "in_tokens": tin, "out_tokens": tout, "reasoning_tokens": sum(r["reasoning_tokens"] for r in rows),
        "total_cost_usd": round(cost_total, 4),
        "rows": rows,
    }
    if extra_meta:
        summary.update(extra_meta)
    return summary


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", required=True)
    ap.add_argument("--prompt", required=True)
    ap.add_argument("--data", default=os.path.join(HERE, "data", "test.jsonl"))
    ap.add_argument("--shots", default=os.path.join(HERE, "data", "train.jsonl"))
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--seed", type=int, default=7, help="shuffles row order and picks few-shot examples")
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--max_tokens", type=int, default=2048)
    ap.add_argument("--extra", default="", help='extra JSON body fields, e.g. {"reasoning_effort":"low"}')
    ap.add_argument("--out")
    ap.add_argument("--tag", default="")
    args = ap.parse_args()

    rows_in = load_jsonl(args.data)
    rng = random.Random(args.seed)
    rng.shuffle(rows_in)
    if args.limit:
        rows_in = rows_in[: args.limit]
    prompt_name = os.path.splitext(os.path.basename(args.prompt))[0]
    system_prompt = build_system(args.prompt, args.shots, seed=args.seed)
    extra = json.loads(args.extra) if args.extra else None
    tag = args.tag or f"{fw.SHORT[args.model]}_{prompt_name}_s{args.seed}"
    t0 = time.time()
    with ThreadPoolExecutor(args.workers) as ex:
        rows = list(ex.map(lambda e: run_one(args.model, system_prompt, e, args.max_tokens, extra, tag), rows_in))
    summary = summarize(args.model, prompt_name, rows, {"seed": args.seed, "extra": extra, "wall_s": round(time.time() - t0, 1),
                                                          "data": os.path.basename(args.data)})
    out = args.out or os.path.join(HERE, "results", f"{fw.SHORT[args.model]}_{prompt_name}_s{args.seed}.json")
    with open(out, "w") as f:
        json.dump(summary, f, indent=2)
    print(f"\n{args.model} + {prompt_name}: F1 {summary['accuracy']:.3f} | exact {summary['exact_accuracy']:.3f} | invalid {summary['invalid_outputs']} | p50 {summary['p50_latency_s']}s p95 {summary['p95_latency_s']}s | ${summary['cost_per_1k_requests_usd']:.3f}/1k | run cost ${summary['total_cost_usd']:.3f} | ledger ${fw.ledger_total():.3f}")
    print(f"saved {out}")


if __name__ == "__main__":
    main()
