#!/usr/bin/env python3
"""LoRA SFT of Muse Glimmer 30B on the Fireworks Serverless Training API, then score the checkpoint.

Why this path: it is the only way tonight to score a tuned model without a dedicated deployment
(sampler checkpoints are served from the shared pool). Training on Muse Glimmer 30B is free until
2026-11-30 per docs.fireworks.ai/fine-tuning/models.md and fireworks.ai/pricing; sampling is billed
per token (prefill $1.96/M, sample $4.88/M) and is logged to ledger.csv.

    venv311/bin/python sft_serverless.py --dry-run            # tokenize only, print token counts (no API)
    venv311/bin/python sft_serverless.py --train              # train, save checkpoint path to results/sft_checkpoint.json
    venv311/bin/python sft_serverless.py --eval <snapshot>    # sample the test set from a checkpoint and score it
    venv311/bin/python sft_serverless.py --eval base          # same for the untuned base (control row)

Requires Python 3.11 (venv311) and FIREWORKS_API_KEY.
"""
import argparse
import csv
import json
import os
import random
import statistics
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from score import extract_regex, score_row  # noqa: E402

BASE_MODEL = "accounts/fireworks/models/muse-glimmer-30b"
TOKENIZER = "meta-models/Muse-Glimmer-30B"
SERVERLESS_URL = "https://api.fireworks.ai/training/v1/serverless"
PRICE_PREFILL, PRICE_SAMPLE, PRICE_TRAIN = 1.96, 4.88, 0.0  # $/M; train is free until 2026-11-30 (see docstring)
LEDGER = os.path.join(HERE, "ledger.csv")


def ledger_append(model, in_tok, out_tok, cost, note):
    new = not os.path.exists(LEDGER)
    with open(LEDGER, "a", newline="") as f:
        w = csv.writer(f)
        if new:
            w.writerow(["timestamp", "model", "in_tokens", "out_tokens", "cost", "note"])
        w.writerow([time.strftime("%Y-%m-%dT%H:%M:%S"), model, in_tok, out_tok, f"{cost:.6f}", note])


def load_jsonl(p):
    return [json.loads(l) for l in open(p) if l.strip()]


def get_tokenizer():
    from transformers import AutoTokenizer
    return AutoTokenizer.from_pretrained(TOKENIZER)


def _ids(tok, text):
    """Tokenize template text ourselves: newer transformers return a BatchEncoding from apply_chat_template(tokenize=True)."""
    return list(tok(text, add_special_tokens=False)["input_ids"])


def render(tok, system, user, assistant=None):
    """Return (prompt_ids, full_ids). Reasoning strength low so the tuned model answers directly."""
    msgs = [{"role": "system", "content": system}, {"role": "user", "content": user}]
    prompt = _ids(tok, tok.apply_chat_template(msgs, tokenize=False, add_generation_prompt=True, reasoning_strength="low"))
    if assistant is None:
        return list(prompt), None
    full = _ids(tok, tok.apply_chat_template(msgs + [{"role": "assistant", "content": assistant}], tokenize=False, reasoning_strength="low"))
    assert full[: len(prompt)] == list(prompt), "chat template prefix mismatch"
    return list(prompt), full


def build_datums(tok, rows, system):
    from fireworks.training import sdk
    datums, n_train_tok, n_tok = [], 0, 0
    for r in rows:
        prompt, full = render(tok, system, r["text"], r["gold"])
        weights = [0.0] * (len(prompt) - 1) + [1.0] * (len(full) - len(prompt))
        tokens = full
        datums.append(sdk.Datum(
            model_input=sdk.ModelInput.from_ints(tokens[:-1]),
            loss_fn_inputs={
                "target_tokens": sdk.TensorData(data=tokens[1:], dtype="int64", shape=[len(tokens) - 1]),
                "weights": sdk.TensorData(data=weights, dtype="float32", shape=[len(weights)]),
            }))
        n_train_tok += int(sum(weights))
        n_tok += len(tokens)
    return datums, n_tok, n_train_tok


def train(args):
    from fireworks.training.sdk import FiretitanServiceClient
    from fireworks.training import sdk
    tok = get_tokenizer()
    rows = load_jsonl(os.path.join(HERE, "data", "train.jsonl"))
    system = open(os.path.join(HERE, "prompts", "v1_plain.txt")).read().strip()
    datums, n_tok, n_train_tok = build_datums(tok, rows, system)
    print(f"{len(datums)} examples, {n_tok} tokens/epoch ({n_train_tok} trained), epochs={args.epochs} -> "
          f"{n_tok * args.epochs} training tokens, est. train cost ${n_tok * args.epochs * PRICE_TRAIN / 1e6:.3f}")
    if n_tok * args.epochs > 300_000:
        sys.exit("refusing: more than 300k training tokens")
    if args.dry_run:
        return
    service = FiretitanServiceClient(api_key=os.environ["FIREWORKS_API_KEY"], base_url=SERVERLESS_URL)
    tc = service.create_lora_training_client(base_model=BASE_MODEL, rank=args.rank)
    print("training session", getattr(service, "training_session_id", None), "run", getattr(tc, "run_id", None))
    rng = random.Random(0)
    step, log = 0, []
    total_steps = args.epochs * ((len(datums) + args.batch - 1) // args.batch)
    for ep in range(args.epochs):
        order = list(range(len(datums)))
        rng.shuffle(order)
        for i in range(0, len(order), args.batch):
            batch = [datums[j] for j in order[i:i + args.batch]]
            lr = args.lr * max(0.1, 1 - step / total_steps)  # linear decay to 10%
            fb = tc.forward_backward(batch, "cross_entropy").result()
            opt = tc.optim_step(sdk.AdamParams(learning_rate=lr)).result()
            metrics = getattr(fb, "metrics", None) or {}
            loss = metrics.get("loss") if isinstance(metrics, dict) else None
            step += 1
            log.append({"step": step, "epoch": ep, "lr": lr, "loss": loss, "metrics": str(metrics)[:300]})
            print(f"step {step}/{total_steps} epoch {ep} lr {lr:.2e} loss {loss}", flush=True)
    name = f"regex-sft-{int(time.time())}"
    path = tc.save_weights_for_sampler(name).result().path
    print("checkpoint:", path, flush=True)
    service.close()  # free the account's single concurrent serverless-training slot for sibling sessions
    ledger_append(BASE_MODEL + " (serverless training)", n_tok * args.epochs, 0, n_tok * args.epochs * PRICE_TRAIN / 1e6, "sft train (free until 2026-11-30)")
    with open(os.path.join(HERE, "results", "sft_checkpoint.json"), "w") as f:
        json.dump({"checkpoint": path, "base_model": BASE_MODEL, "rank": args.rank, "epochs": args.epochs, "batch": args.batch,
                   "lr": args.lr, "examples": len(datums), "tokens_per_epoch": n_tok, "trained_tokens_per_epoch": n_train_tok,
                   "session": getattr(service, "training_session_id", None), "log": log}, f, indent=1)
    service.close()


def evaluate(args):
    from fireworks.training.sdk import FiretitanServiceClient
    from fireworks.training import sdk
    tok = get_tokenizer()
    rows = load_jsonl(os.path.join(HERE, "data", "test.jsonl"))
    if args.limit:
        rows = rows[: args.limit]
    system = open(os.path.join(HERE, "prompts", "v1_plain.txt")).read().strip()
    service = FiretitanServiceClient(api_key=os.environ["FIREWORKS_API_KEY"], base_url=SERVERLESS_URL)
    if args.eval == "base":
        sampler = service.create_sampling_client(base_model=BASE_MODEL, tokenizer=tok)
        label = "muse-glimmer-30b_base"
    else:
        sampler = service.create_sampling_client(model_path=args.eval, tokenizer=tok)
        label = "muse-glimmer-30b_sft"
    eot = tok.convert_tokens_to_ids("<|eot|>")
    msg_id = tok.convert_tokens_to_ids("<|message|>")
    params = sdk.SamplingParams(max_tokens=args.max_tokens, temperature=0, stop=[eot])
    # Muse's template renders the answer turn as "<|start|>assistant to=user<|message|>ANSWER<|eot|>". Left to itself the base
    # model first opens a "to=self" reasoning channel; prefilling " to=user<|message|>" forces a direct answer, which is the same
    # reasoning-off setting the serverless models get (reasoning_effort none/low). Base and SFT are evaluated identically.
    _, full_probe = render(tok, system, "probe", "x")
    prefill = full_probe[len(render(tok, system, "probe")[0]): len(full_probe) - full_probe[::-1].index(msg_id)]
    out_rows, lat, in_tok, out_tok = [], [], 0, 0
    for i, r in enumerate(rows):
        prompt, _ = render(tok, system, r["text"])
        prompt = prompt + prefill
        t0 = time.time()
        res = sampler.sample(prompt=sdk.ModelInput.from_ints(prompt), num_samples=1, sampling_params=params).result()
        dt = time.time() - t0
        seq = (res.sequences or [None])[0]
        toks = list(seq.tokens) if seq is not None else []
        text = tok.decode(toks, skip_special_tokens=False)
        raw = text
        # Muse answers as "to=user<|message|>...<|eot|>" after "<|start|>assistant"; keep what is after <|message|>
        if "<|message|>" in raw:
            raw = raw.split("<|message|>")[-1]
        raw = raw.replace("<|eot|>", "").strip()
        pred = extract_regex(raw)
        sc = score_row(pred, r["positives"], r["negatives"])
        in_tok += len(prompt)
        out_tok += len(toks)
        lat.append(dt)
        out_rows.append({"id": r["id"], "text": r["text"], "gold": r["gold"], "raw": text, "pred": pred, "valid": sc["valid"],
                         "correct": sc["correct"], "soft": sc["soft"], "pos_ok": sc["pos_ok"], "neg_ok": sc["neg_ok"],
                         "timeouts": sc["timeouts"], "error": sc["error"], "latency": round(dt, 3), "in_tokens": len(prompt),
                         "out_tokens": len(toks), "reasoning_tokens": 0, "finish_reason": str(getattr(seq, "stop_reason", None)),
                         "confidence": None})
        print(("✓" if sc["correct"] else ("✗" if sc["valid"] else "!")), f"{i+1:3d}/{len(rows)} {dt:5.2f}s {r['text'][:50]!r} -> {str(pred)[:40]!r}", flush=True)
    sampler.close()
    service.close()
    n = len(out_rows)
    cost = (in_tok * PRICE_PREFILL + out_tok * PRICE_SAMPLE) / 1e6
    ledger_append(BASE_MODEL + " (sampler)", in_tok, out_tok, cost, f"eval {label}")
    ls = sorted(lat)
    summary = {"model": f"accounts/raheeldeal/{label}", "prompt": "v1_plain", "mock": False, "n": n,
               "accuracy": round(sum(r["correct"] for r in out_rows) / n, 4),
               "soft_score": round(sum(r["soft"] for r in out_rows) / n, 4),
               "invalid_outputs": sum(not r["valid"] for r in out_rows), "timeouts": sum(r["timeouts"] for r in out_rows),
               "truncated": 0, "p50_latency_s": round(statistics.median(lat), 3), "p95_latency_s": round(ls[int(0.95 * (n - 1))], 3),
               "cost_per_1k_requests_usd": round(cost / n * 1000, 4), "in_tokens": in_tok, "out_tokens": out_tok,
               "cost_usd": round(cost, 5), "seed": 0, "max_tokens": args.max_tokens, "json_mode": False,
               "reasoning_effort": "low (chat template)", "checkpoint": args.eval, "rows": out_rows,
               "note": "sampler pricing (serverless training pool), not serverless inference pricing"}
    out = os.path.join(HERE, "results", f"{label}_v1_plain.json")
    with open(out, "w") as f:
        json.dump(summary, f, indent=1, ensure_ascii=False)
    print(f"\n{label}: accuracy {summary['accuracy']:.1%} | soft {summary['soft_score']:.3f} | invalid {summary['invalid_outputs']} | "
          f"p50 {summary['p50_latency_s']}s | ${summary['cost_per_1k_requests_usd']:.4f}/1k | cost ${cost:.4f}\nsaved {out}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--train", action="store_true")
    ap.add_argument("--eval", help="checkpoint path from --train, or 'base'")
    ap.add_argument("--epochs", type=int, default=2)
    ap.add_argument("--batch", type=int, default=16)
    ap.add_argument("--rank", type=int, default=8)
    ap.add_argument("--lr", type=float, default=1e-4)
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--max-tokens", type=int, default=160)
    args = ap.parse_args()
    if args.eval:
        evaluate(args)
    elif args.train or args.dry_run:
        train(args)
    else:
        print(__doc__)


if __name__ == "__main__":
    main()
