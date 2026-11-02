#!/usr/bin/env python3
"""LoRA SFT of Muse Glimmer 30B on the Fireworks Serverless Training API, then base-vs-tuned eval on the locked test set.

Why this path: trained LoRAs can only be served on dedicated deployments (forbidden by PROTOCOL rule 3), but a
serverless-training sampler checkpoint can be sampled directly. Muse Glimmer 30B LoRA SFT is $0 until 2026-11-30
(docs.fireworks.ai/fine-tuning/models, fireworks.ai/pricing); eval sampling is billed per token ($1.96/M prefill, $4.88/M sampled).

Run with the venv:  sdk/venv/bin/python sft_serverless.py [--dry-run] [--skip-base] [--limit N]
"""
import argparse, csv, datetime, json, os, random, re, statistics, sys, time
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
os.environ.setdefault("HF_HOME", os.path.join(HERE, "sdk", "hf_cache"))
from score import score

BASE_MODEL = "accounts/fireworks/models/muse-glimmer-30b"
TOKENIZER = "meta-models/Muse-Glimmer-30B"
PRICE_PREFILL, PRICE_SAMPLE = 1.96, 4.88   # $/M, serverless training pool, fireworks.ai/pricing 2026-11-01
DB_ROOT = os.path.join(HERE, "raw", "zip", "spider_data", "database")
LEDGER = os.path.join(HERE, "ledger.csv")

def user_message(ex):
    return f"Schema:\n{ex['schema']}\n\nQuestion: {ex['question']}\nSQL:"

SYSTEM = "Reasoning strength: low.\n" + open(os.path.join(HERE, "prompts", "v1_plain.txt")).read().strip()

def msgs(ex, with_answer):
    m = [{"role": "system", "content": SYSTEM}, {"role": "user", "content": user_message(ex)}]
    if with_answer:
        m.append({"role": "assistant", "content": ex["gold_sql"]})
    return m

def ledger_add(model, ti, to, cost, note):
    new = not os.path.exists(LEDGER)
    with open(LEDGER, "a", newline="") as f:
        w = csv.writer(f)
        if new: w.writerow(["timestamp", "model", "in_tokens", "out_tokens", "cost", "note"])
        w.writerow([datetime.datetime.now().isoformat(timespec="seconds"), model, ti, to, f"{cost:.6f}", note])

def encode_ids(tok, m, gen):
    text = tok.apply_chat_template(m, tokenize=False, add_generation_prompt=gen)
    return list(tok(text, add_special_tokens=False)["input_ids"])

def build_datums(tok, rows, sdk, max_len=2048):
    datums, skipped, meta = [], 0, []
    for ex in rows:
        prefix = encode_ids(tok, msgs(ex, False), True)
        full = encode_ids(tok, msgs(ex, True), False)
        if full[:len(prefix)] != prefix or len(full) > max_len:
            skipped += 1; continue
        w = [0.0] * len(prefix) + [1.0] * (len(full) - len(prefix))
        d = sdk.Datum(model_input=sdk.ModelInput.from_ints(full[:-1]),
                      loss_fn_inputs={"target_tokens": full[1:], "weights": w[1:]})
        datums.append(d); meta.append({"ntok": len(full), "nloss": int(sum(w)), "targets": full[1:], "w": w[1:]})
    return datums, skipped, meta

def parse_answer(tok, tokens):
    text = tok.decode(tokens, skip_special_tokens=False)
    # keep the last channel addressed to the user; drop reasoning (to=self)
    parts = re.split(r"<\|start\|>assistant(?: to=\w+)?<\|message\|>", text)
    segs = [p for p in parts if p.strip()]
    if "<|message|>" in text:
        segs = text.split("<|message|>")
    ans = segs[-1] if segs else text
    ans = re.split(r"<\|eot\|>|<\|end_of_text\|>|<\|eom\|>", ans)[0]
    return ans.strip(), text

def evaluate(service, tok, sdk, model_path, base_model, rows, label, max_tokens, args):
    if model_path:
        sampler = service.create_sampling_client(model_path=model_path, tokenizer=tok)
    else:
        sampler = service.create_sampling_client(base_model=base_model, tokenizer=tok)
    params = sdk.SamplingParams(max_tokens=max_tokens, temperature=0.0, stop=["<|eot|>", "<|end_of_text|>"])
    out, ptok, stok = [], 0, 0
    try:
        prompts = []
        for ex in rows:
            ids = encode_ids(tok, msgs(ex, False), True)
            prompts.append(sdk.ModelInput.from_ints(ids))
        futs = []
        for i in range(0, len(prompts), args.concurrency):
            futs.extend(sampler.sample(prompt=p, num_samples=1, sampling_params=params) for p in prompts[i:i + args.concurrency])
        t_all = time.time()
        for ex, p, fut in zip(rows, prompts, futs):
            t0 = time.time()
            res = fut.result() if hasattr(fut, "result") else fut
            lat = time.time() - t0
            toks = list(res.sequences[0].tokens)
            ans, raw_text = parse_answer(tok, toks)
            ptok += len(p.to_ints()); stok += len(toks)
            db = os.path.join(DB_ROOT, ex["db_id"], ex["db_id"] + ".sqlite")
            s = score(ans, ex["gold_sql"], db)
            out.append({"id": ex["id"], "db_id": ex["db_id"], "question": ex["question"], "gold_sql": ex["gold_sql"], "raw": raw_text[-1500:],
                        "pred_sql": s["pred_sql"], "correct": s["exec_match"], "exact": s["exact_match"], "invalid": s["invalid"],
                        "error": s["error"], "latency": lat, "in_tokens": len(p.to_ints()), "out_tokens": len(toks),
                        "truncated": len(toks) >= max_tokens})
            print(("✓" if s["exec_match"] else ("!" if s["invalid"] else "✗")), f"{label} {ex['db_id']:26s} {len(toks):4d} tok  {ex['question'][:50]}", flush=True)
    finally:
        sampler.close()
    cost = (ptok * PRICE_PREFILL + stok * PRICE_SAMPLE) / 1e6
    ledger_add(f"serverless-sampler:{BASE_MODEL.split('/')[-1]}:{label}", ptok, stok, cost, f"sft eval {label} n={len(rows)}")
    n = len(out); lats = sorted(r["latency"] for r in out)
    summ = {"model": f"{BASE_MODEL}:{label}", "prompt": "v1_plain_sft" if label == "tuned" else "v1_plain", "mock": False, "n": n,
            "accuracy": round(sum(r["correct"] for r in out) / n, 4), "exact_match": round(sum(r["exact"] for r in out) / n, 4),
            "invalid_outputs": sum(r["invalid"] for r in out), "truncated": sum(r["truncated"] for r in out),
            "p50_latency_s": round(statistics.median(lats), 3), "p95_latency_s": round(lats[int(0.95 * (n - 1))], 3),
            "in_tokens": ptok, "out_tokens": stok, "cost_total_usd": round(cost, 5),
            # serving-cost basis for the frontier chart: a LoRA served on Fireworks costs the same as its base model.
            # Muse Glimmer 30B has no public serverless inference price; use the 30B-class nemotron-lightning-3p5-30b-a3b rate as proxy.
            "cost_per_1k_requests_usd": round((ptok * 0.05 + stok * 0.20) / 1e6 / n * 1000, 4),
            "cost_basis_note": "serving cost estimated at 30B-class serverless rate ($0.05/M in, $0.20/M out); eval sampling actually billed at training-pool rates (cost_total_usd)",
            "rows": out}
    path = os.path.join(HERE, "results", f"muse-glimmer-30b_{'v1_plain_sft' if label == 'tuned' else 'v1_plain_base'}.json")
    json.dump(summ, open(path, "w"), indent=1)
    print(f"\n{label}: exec acc {summ['accuracy']:.1%} | exact {summ['exact_match']:.1%} | invalid {summ['invalid_outputs']} | truncated {summ['truncated']} | sampling cost ${cost:.3f}\nsaved {path}", flush=True)
    return summ

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true"); ap.add_argument("--skip-base", action="store_true")
    ap.add_argument("--limit", type=int, default=0); ap.add_argument("--epochs", type=int, default=2)
    ap.add_argument("--batch-size", type=int, default=16); ap.add_argument("--lr", type=float, default=1e-4)
    ap.add_argument("--rank", type=int, default=8); ap.add_argument("--base-max-tokens", type=int, default=700)
    ap.add_argument("--tuned-max-tokens", type=int, default=200); ap.add_argument("--concurrency", type=int, default=8)
    args = ap.parse_args()
    from transformers import AutoTokenizer
    from fireworks.training import sdk
    tok = AutoTokenizer.from_pretrained(TOKENIZER)
    train = [json.loads(l) for l in open(os.path.join(HERE, "data", "train.jsonl"))]
    test = [json.loads(l) for l in open(os.path.join(HERE, "data", "test.jsonl"))]
    if args.limit: test = test[:args.limit]
    datums, skipped, meta = build_datums(tok, train, sdk)
    ntok = sum(m["ntok"] for m in meta)
    nloss = sum(m["nloss"] for m in meta)
    print(f"datums {len(datums)} (skipped {skipped}); total tokens {ntok}, loss tokens {nloss}; x{args.epochs} epochs = {ntok*args.epochs} training tokens")
    if args.dry_run:
        d = datums[0]; ids = list(d.model_input.to_ints())
        print(tok.decode(ids[-60:]), "\n--- targets with weight 1:", tok.decode([t for t, w in zip(meta[0]["targets"], meta[0]["w"]) if w > 0]))
        return
    from fireworks.training.sdk import FiretitanServiceClient
    service = FiretitanServiceClient(api_key=os.environ["FIREWORKS_API_KEY"], base_url="https://api.fireworks.ai/training/v1/serverless")
    if hasattr(service, "_enable_serverless_supervised_409_retry"):
        service._enable_serverless_supervised_409_retry()
    log = open(os.path.join(HERE, "results", "sft_metrics.jsonl"), "a")
    try:
        if not args.skip_base:
            evaluate(service, tok, sdk, None, BASE_MODEL, test, "base", args.base_max_tokens, args)
        tc = service.create_lora_training_client(base_model=BASE_MODEL, rank=args.rank, alpha=32, train_mlp=True, train_attn=True, train_unembed=True)
        print(f"session={service.training_session_id} run={tc.run_id}", flush=True)
        adam = sdk.AdamParams(learning_rate=args.lr, beta1=0.9, beta2=0.999, eps=1e-8, weight_decay=0.0, grad_clip_norm=1.0)
        rng = random.Random(0); step = 0
        for ep in range(args.epochs):
            order = list(range(len(datums))); rng.shuffle(order)
            for s0 in range(0, len(order), args.batch_size):
                batch = [datums[i] for i in order[s0:s0 + args.batch_size]]
                fb = tc.forward_backward(batch, "cross_entropy").result()
                tc.optim_step(adam).result(); step += 1
                m = dict(getattr(fb, "metrics", None) or {})
                loss = m.get("loss:sum", 0.0) / max(float(m.get("response_tokens") or m.get("num_loss_tokens") or 1.0), 1.0)
                row = {"step": step, "epoch": ep + 1, "loss": round(loss, 4)}; log.write(json.dumps(row) + "\n"); log.flush(); print(row, flush=True)
        snap = tc.save_weights_for_sampler(f"t2sql-{datetime.datetime.now():%H%M%S}").result().path
        print("sampler checkpoint:", snap, flush=True)
        json.dump({"checkpoint": snap, "session": service.training_session_id, "run": tc.run_id, "steps": step, "epochs": args.epochs,
                   "rank": args.rank, "lr": args.lr, "train_tokens": ntok * args.epochs}, open(os.path.join(HERE, "results", "sft_job.json"), "w"), indent=1)
        ledger_add(f"serverless-train:{BASE_MODEL.split('/')[-1]}", ntok * args.epochs, 0, 0.0, "LoRA SFT, promotional $0 (free until 2026-11-30)")
        evaluate(service, tok, sdk, snap, None, test, "tuned", args.tuned_max_tokens, args)
    finally:
        log.close(); service.close()

if __name__ == "__main__":
    main()
