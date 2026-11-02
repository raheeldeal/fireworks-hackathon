#!/usr/bin/env python3
"""LoRA SFT of Muse Glimmer 30B on the Fireworks Serverless Training API, then score base and tuned checkpoints on
the locked test set with score.py. No deployment is created (PROTOCOL rule 3). Uses only the PyPI SDK
(`fireworks-ai[training]`) and the Hugging Face tokenizer's chat template (no cookbook code).

  .venv311/bin/python train_sft.py --epochs 1 [--eval-rows 200] [--skip-base] [--dry-run]

Promotion: docs.fireworks.ai/fine-tuning/models.md and .../cookbook/muse-glimmer.md state Muse Glimmer 30B LoRA SFT is
free via the Serverless Training API until 2026-11-30 (Pacific). This script refuses to train after that date.
Evaluation sampling is PAID at the serverless sampling rates (prefill $1.96/M, sample $4.88/M, 2026-11-01) and is
appended to ledger.csv. Results: results/sft_muse-glimmer-30b_{base,tuned}_json_v1_plain.json (run_eval shape).
"""
import argparse, csv, json, os, random, statistics, sys, time
from datetime import datetime, timedelta, timezone
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from score import score, parse_call

BASE_MODEL = "accounts/fireworks/models/muse-glimmer-30b"
TOKENIZER = "meta-models/Muse-Glimmer-30B"
PROMO_DEADLINE = datetime(2026, 12, 1, tzinfo=timezone(timedelta(hours=-8)))
PREFILL, SAMPLE = 1.96, 4.88      # $/M, serverless training sampling rates for Muse Glimmer 30B
SPEND_CAP = 3.00
STOP = ["<|eot|>", "<|end_of_text|>"]

def ledger_total(p):
    return sum(float(r["cost"]) for r in csv.DictReader(open(p))) if os.path.exists(p) else 0.0

def ledger_append(p, model, ti, to, cost, note):
    new = not os.path.exists(p)
    with open(p, "a", newline="") as f:
        w = csv.writer(f)
        if new: w.writerow(["timestamp", "model", "in_tokens", "out_tokens", "cost", "note"])
        w.writerow([time.strftime("%Y-%m-%dT%H:%M:%S"), model, ti, to, f"{cost:.6f}", note])

def render(tok, messages, add_gen):
    return tok.apply_chat_template(messages, tokenize=False, add_generation_prompt=add_gen)

def test_messages(ex, system_prompt):
    tools_text = json.dumps([t["function"] for t in ex["tools"]], ensure_ascii=False)
    msgs = [{"role": "system", "content": system_prompt + "\n\nAvailable tools (JSON):\n" + tools_text}]
    msgs += [{"role": m["role"], "content": m["content"]} for m in ex["messages"]]
    return msgs

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--epochs", type=int, default=1)
    ap.add_argument("--batch-size", type=int, default=16)
    ap.add_argument("--learning-rate", type=float, default=1e-4)
    ap.add_argument("--lora-rank", type=int, default=8)
    ap.add_argument("--max-seq-len", type=int, default=4096)
    ap.add_argument("--eval-rows", type=int, default=200)
    ap.add_argument("--max-eval-tokens", type=int, default=300)
    ap.add_argument("--skip-base", action="store_true", help="do not score the base checkpoint (saves ~$0.3)")
    ap.add_argument("--dry-run", action="store_true", help="render and count tokens only; no API calls")
    ap.add_argument("--ledger", default=os.path.join(HERE, "ledger.csv"))
    args = ap.parse_args()

    if datetime.now(timezone.utc) >= PROMO_DEADLINE:
        sys.exit("Muse Glimmer free-SFT promotion has ended (2026-11-30). Not training (PROTOCOL rule 4).")
    spent = ledger_total(args.ledger)
    if spent >= SPEND_CAP:
        sys.exit(f"SPEND CAP: ledger ${spent:.2f} >= ${SPEND_CAP}")

    from transformers import AutoTokenizer
    tok = AutoTokenizer.from_pretrained(TOKENIZER)
    system_prompt = open(os.path.join(HERE, "prompts", "v1_plain.txt")).read().strip()
    train = [json.loads(l) for l in open(os.path.join(HERE, "data", "sft_train.jsonl"))]
    test = [json.loads(l) for l in open(os.path.join(HERE, "data", "test.jsonl"))][: args.eval_rows]

    # ---- build supervised datums: loss only on the assistant turn ----
    datums_raw, total_tokens, loss_tokens, oversized = [], 0, 0, 0
    for r in train:
        p_ids = tok.encode(render(tok, r["messages"][:-1], True), add_special_tokens=False)
        f_ids = tok.encode(render(tok, r["messages"], False), add_special_tokens=False)
        if f_ids[: len(p_ids)] != p_ids:          # template mismatch guard
            n = next((i for i, (a, b) in enumerate(zip(p_ids, f_ids)) if a != b), min(len(p_ids), len(f_ids)))
            p_ids = f_ids[:n]
        if len(f_ids) > args.max_seq_len:
            oversized += 1; continue
        w = [0.0] * len(p_ids) + [1.0] * (len(f_ids) - len(p_ids))
        datums_raw.append((f_ids, w)); total_tokens += len(f_ids); loss_tokens += len(f_ids) - len(p_ids)
    est_eval_prompt = sum(len(tok.encode(render(tok, test_messages(ex, system_prompt), True), add_special_tokens=False)) for ex in test)
    est_eval_cost = (est_eval_prompt * PREFILL + len(test) * 80 * SAMPLE) / 1e6
    print(f"train rows {len(datums_raw)} (dropped {oversized} > {args.max_seq_len} tokens); total tokens {total_tokens:,}; loss tokens {loss_tokens:,}")
    print(f"eval: {len(test)} rows, ~{est_eval_prompt:,} prompt tokens; est. sampling cost per pass ${est_eval_cost:.3f}; training $0 (promotion)")
    if total_tokens * args.epochs > 300_000:
        sys.exit("training tokens x epochs exceed 300k (PROTOCOL rule 4)")
    if args.dry_run:
        return

    from fireworks.training import sdk
    from fireworks.training.sdk import FiretitanServiceClient
    service = FiretitanServiceClient(api_key=os.environ["FIREWORKS_API_KEY"], base_url="https://api.fireworks.ai/training/v1/serverless")
    run_dir = os.path.join(HERE, "results", "sft_logs"); os.makedirs(run_dir, exist_ok=True)
    log = open(os.path.join(run_dir, "metrics.jsonl"), "a")
    tc = service.create_lora_training_client(base_model=BASE_MODEL, rank=args.lora_rank, alpha=32)
    print(f"session={getattr(service, 'training_session_id', None)} run={getattr(tc, 'run_id', None)}", flush=True)
    params = sdk.SamplingParams(max_tokens=args.max_eval_tokens, temperature=0.0, stop=STOP)

    def evaluate(label):
        snap = tc.save_weights_for_sampler(f"fc-{label}").result().path
        print(f"checkpoint {label}: {snap}", flush=True)
        sampler = service.create_sampling_client(model_path=snap, tokenizer=tok)
        rows, pt, st = [], 0, 0
        t_all = time.time()
        try:
            prompts = [sdk.types.ModelInput.from_ints(tok.encode(render(tok, test_messages(ex, system_prompt), True), add_special_tokens=False)) for ex in test]
            futs = [sampler.sample(prompt=p, num_samples=1, sampling_params=params) for p in prompts]
            for i, (ex, p, fut) in enumerate(zip(test, prompts, futs)):
                t0 = time.time(); res = fut.result(); lat = time.time() - t0
                out = list(res.sequences[0].tokens)
                text = tok.decode(out, skip_special_tokens=True)
                pt += len(p.to_ints()); st += len(out)
                pred = parse_call(text)
                s = score(pred, ex["acceptable"])
                rows.append({"id": ex["id"], "source": ex["source"], "gold": ex["answer"], "pred": pred, "strict": s["strict"], "partial": s["partial"],
                             "invalid": s["invalid"], "name_ok": s["name_ok"], "reason": s["reason"], "latency": round(lat, 3),
                             "in_tokens": len(p.to_ints()), "out_tokens": len(out), "reasoning_tokens": 0, "confidence": None,
                             "raw": text[:400], "pred_source": "content", "stop_reason": str(getattr(res.sequences[0], "stop_reason", ""))})
                if (i + 1) % 20 == 0: print(f"{label}: {i+1}/{len(test)} strict so far {sum(r['strict'] for r in rows)/(i+1):.1%}", flush=True)
        finally:
            close = getattr(sampler, "close", None)
            if close: close()
            cost = (pt * PREFILL + st * SAMPLE) / 1e6
            ledger_append(args.ledger, f"{BASE_MODEL}#sampler-{label}", pt, st, cost, f"sft eval {label}")
        n = len(rows); lats = sorted(r["latency"] for r in rows)
        by = {}
        for r in rows:
            b = by.setdefault(r["source"].replace("BFCL_v4_", "").replace(".json", ""), [0, 0]); b[0] += r["strict"]; b[1] += 1
        summary = {"model": f"{BASE_MODEL}#lora-sft-{label}", "prompt": "v1_plain", "mode": "json", "shots": 0, "tool_choice": "n/a",
                   "response_format": "none", "seed": 0, "mock": False, "n": n, "accuracy": round(sum(r["strict"] for r in rows) / n, 4),
                   "accuracy_partial": round(sum(r["partial"] for r in rows) / n, 4), "invalid_outputs": sum(r["invalid"] for r in rows), "api_errors": 0,
                   "p50_latency_s": round(statistics.median(lats), 3), "p95_latency_s": round(lats[int(0.95 * (n - 1))], 3),
                   "cost_per_1k_requests_usd": round(cost / n * 1000, 4), "total_cost_usd": round(cost, 5), "in_tokens": pt, "out_tokens": st,
                   "reasoning_tokens": 0, "accuracy_by_source": {k: round(v[0] / v[1], 3) for k, v in by.items()}, "wall_s": round(time.time() - t_all, 1),
                   "note": "cost at serverless-training sampler rates (prefill $1.96/M, sample $4.88/M); production serving would be an on-demand deployment",
                   "rows": rows}
        out = os.path.join(HERE, "results", f"sft_muse-glimmer-30b_{label}_json_v1_plain.json")
        json.dump(summary, open(out, "w"), indent=1, ensure_ascii=False)
        print(f"{label}: strict {summary['accuracy']:.1%} partial {summary['accuracy_partial']:.1%} invalid {summary['invalid_outputs']} ${cost:.3f} -> {out}", flush=True)
        log.write(json.dumps({"eval": label, "accuracy": summary["accuracy"], "cost": cost}) + "\n"); log.flush()
        return summary

    try:
        if not args.skip_base:
            evaluate("base")
        datums = [sdk.Datum(model_input=sdk.types.ModelInput.from_ints(ids[:-1]), loss_fn_inputs={"target_tokens": ids[1:], "weights": w[1:]})
                  for ids, w in datums_raw]
        adam = sdk.AdamParams(learning_rate=args.learning_rate, beta1=0.9, beta2=0.999, eps=1e-8, weight_decay=0.0, grad_clip_norm=1.0)
        rng = random.Random(0); step = 0
        for epoch in range(args.epochs):
            order = list(range(len(datums))); rng.shuffle(order)
            for start in range(0, len(order), args.batch_size):
                batch = [datums[i] for i in order[start:start + args.batch_size]]
                fb = tc.forward_backward(batch, "cross_entropy").result()
                opt = tc.optim_step(adam, emit_grad_norm_metrics=True).result()
                step += 1
                m = dict(getattr(fb, "metrics", None) or {})
                ntok = m.get("response_tokens") or m.get("num_loss_tokens") or 1.0
                row = {"step": step, "epoch": epoch + 1, "loss": round(m.get("loss:sum", 0.0) / max(float(ntok), 1.0), 4),
                       **{k: v for k, v in (getattr(opt, "metrics", None) or {}).items() if "grad" in k}}
                log.write(json.dumps(row) + "\n"); log.flush(); print(json.dumps(row), flush=True)
        ledger_append(args.ledger, BASE_MODEL + "#train", total_tokens * args.epochs, 0, 0.0, "sft training (free promotion until 2026-11-30)")
        evaluate("tuned")
    finally:
        log.close(); service.close()
        print("session closed; no deployment created", flush=True)

if __name__ == "__main__":
    main()
