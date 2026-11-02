#!/usr/bin/env python3
"""Phase 7: free LoRA SFT of Muse Glimmer 30B on the Fireworks *serverless* training API, scored via the
serverless sampler (NO dedicated deployment is ever created). Runs under sft/venv (Python 3.11, fireworks-ai>=1.2.30).

  sft/venv/bin/python sft_muse.py plan          # offline: token counts + cost estimate, no API calls
  sft/venv/bin/python sft_muse.py train         # 1 epoch LoRA SFT, saves sampler checkpoint, writes sft/run.json
  sft/venv/bin/python sft_muse.py eval          # samples the locked test set from the checkpoint, writes results/muse-glimmer-30b_sft.json

Evidence training is free (fireworks.ai/pricing, 2026-11-01): "Muse Glimmer 30B SFT is free via UI and Serverless Training
API until 11/30. No credit card required." Eval sampling is billed at serverless-training rates: $1.96/M prefill, $4.88/M sample.
"""
import csv, json, os, statistics, sys, time
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from score import parse, canon

BASE = "accounts/fireworks/models/muse-glimmer-30b"
TOKENIZER = "meta-models/Muse-Glimmer-30B"
SERVERLESS_URL = "https://api.fireworks.ai/training/v1/serverless"
PREFILL_RATE, SAMPLE_RATE = 1.96, 4.88  # $/M tokens, Muse Glimmer serverless training table
EOT = 200008  # <|eot|>
BATCH, LR, RANK, EPOCHS = 16, 1e-4, 8, 1
SPEND_CAP = 3.00
LEDGER = os.path.join(HERE, "ledger.csv")

def ledger_total():
    return sum(float(r["cost"]) for r in csv.DictReader(open(LEDGER))) if os.path.exists(LEDGER) else 0.0

def ledger_add(model, ti, to, cost, tag):
    with open(LEDGER, "a", newline="") as f:
        csv.writer(f).writerow([time.strftime("%Y-%m-%dT%H:%M:%S"), model, ti, to, f"{cost:.6f}", tag])

def tokenizer():
    from transformers import AutoTokenizer
    return AutoTokenizer.from_pretrained(TOKENIZER)

def render(tok, messages, reasoning="none"):
    """Return (full_tokens, prompt_len). Prompt = everything up to and including '<|start|>assistant';
    completion = ' to=user<|message|><label><|eot|>'. Weights are 1 on completion tokens only."""
    prompt = tok.apply_chat_template(messages[:-1], tokenize=False, add_generation_prompt=True, reasoning_strength=reasoning)
    full = tok.apply_chat_template(messages, tokenize=False, reasoning_strength=reasoning)
    assert full.startswith(prompt), "chat template prefix mismatch"
    p = tok.encode(prompt, add_special_tokens=False)
    f = tok.encode(full, add_special_tokens=False)
    assert f[: len(p)] == p, "tokenization prefix mismatch"
    return f, len(p)

def make_datums(tok):
    from fireworks.training.sdk import Datum, ModelInput, types
    rows = [json.loads(l) for l in open(os.path.join(HERE, "data", "sft_train.jsonl"))]
    datums, ntrain, nresp = [], 0, 0
    for r in rows:
        f, plen = render(tok, r["messages"])
        inp, tgt = f[:-1], f[1:]
        w = [1.0 if i + 1 >= plen else 0.0 for i in range(len(tgt))]
        datums.append(Datum(model_input=ModelInput.from_ints(inp),
                            loss_fn_inputs={"weights": types.TensorData(data=w, dtype="float32"),
                                            "target_tokens": types.TensorData(data=tgt, dtype="int64")}))
        ntrain += len(f); nresp += sum(1 for x in w if x)
    return datums, ntrain, nresp

def cmd_plan():
    tok = tokenizer()
    datums, ntrain, nresp = make_datums(tok)
    test = [json.loads(l) for l in open(os.path.join(HERE, "data", "test.jsonl"))]
    sysmsg = open(os.path.join(HERE, "prompts", "v0_sft_short.txt")).read()
    ptoks = sum(len(render(tok, [{"role": "system", "content": sysmsg}, {"role": "user", "content": t["text"]}, {"role": "assistant", "content": "x"}])[0]) for t in test)
    print(f"train rows {len(datums)}, total tokens {ntrain} (response tokens {nresp}), steps/epoch {-(-len(datums)//BATCH)}")
    print(f"training cost: $0.00 (free promo until 2026-11-30)")
    print(f"eval: {len(test)} rows, ~{ptoks} prefill tokens -> ${ptoks*PREFILL_RATE/1e6:.4f} + ~{len(test)*12} sample tokens -> ${len(test)*12*SAMPLE_RATE/1e6:.4f}")
    print(f"ledger so far ${ledger_total():.4f} of ${SPEND_CAP}")

def cmd_train():
    from fireworks.training.sdk import FiretitanServiceClient, AdamParams
    if time.time() > 1796112000:  # 2026-12-01T00:00:00-08:00 = 1796112000 (verified: date -j -f %Y-%m-%dT%H:%M:%S%z): promo over -> abort, never pay
        sys.exit("free Muse Glimmer promo has ended; aborting (no SFT budget)")
    tok = tokenizer()
    datums, ntrain, nresp = make_datums(tok)
    service = FiretitanServiceClient(api_key=os.environ["FIREWORKS_API_KEY"], base_url=SERVERLESS_URL)
    tc = service.create_lora_training_client(base_model=BASE, rank=RANK, seed=20261101)
    print(f"session={service.training_session_id} run={tc.run_id}", flush=True)
    adam = AdamParams(learning_rate=LR)
    step = 0
    for ep in range(EPOCHS):
        for i in range(0, len(datums), BATCH):
            out = tc.forward_backward(datums[i:i + BATCH], "cross_entropy").result()
            tc.optim_step(adam).result()
            step += 1
            nll = out.metrics.get("loss:sum", float("nan")) / max(out.metrics.get("response_tokens", 1.0), 1.0)
            print(f"epoch {ep} step {step} mean_nll {nll:.4f}", flush=True)
    path = tc.save_weights_for_sampler("final").result().path
    info = {"base": BASE, "run_id": tc.run_id, "session": service.training_session_id, "checkpoint": path,
            "rank": RANK, "lr": LR, "batch": BATCH, "epochs": EPOCHS, "train_tokens": ntrain, "steps": step,
            "finished": time.strftime("%Y-%m-%dT%H:%M:%S")}
    json.dump(info, open(os.path.join(HERE, "sft", "run.json"), "w"), indent=2)
    ledger_add(BASE, ntrain, 0, 0.0, "sft_train_free_promo")
    print("saved checkpoint", path)
    service.close()

def cmd_eval():
    from fireworks.training.sdk import FiretitanServiceClient, types
    info = json.load(open(os.path.join(HERE, "sft", "run.json")))
    tok = tokenizer()
    sysmsg = open(os.path.join(HERE, "prompts", "v0_sft_short.txt")).read()
    test = [json.loads(l) for l in open(os.path.join(HERE, "data", "test.jsonl"))]
    service = FiretitanServiceClient(api_key=os.environ["FIREWORKS_API_KEY"], base_url=SERVERLESS_URL)
    sampler = service.create_sampling_client(model_path=info["checkpoint"], tokenizer=tok)
    rows, pin, pout = [], 0, 0
    try:
        for ex in test:
            if ledger_total() + (pin * PREFILL_RATE + pout * SAMPLE_RATE) / 1e6 >= SPEND_CAP:
                raise RuntimeError("SPEND CAP")
            f, plen = render(tok, [{"role": "system", "content": sysmsg}, {"role": "user", "content": ex["text"]}, {"role": "assistant", "content": "x"}])
            prompt_ids = f[:plen]
            t0 = time.time()
            res = sampler.sample(prompt=types.ModelInput.from_ints(prompt_ids), num_samples=1,
                                 sampling_params=types.SamplingParams(max_tokens=40, temperature=0.0, stop=[EOT])).result()
            lat = time.time() - t0
            seq = (res.sequences or [None])[0]
            toks = list(seq.tokens or []) if seq else []
            text = tok.decode(toks, skip_special_tokens=False)
            # completion looks like ' to=user<|message|>label<|eot|>' ; keep what follows <|message|>
            ans = text.split("<|message|>")[-1].replace("<|eot|>", "").strip()
            pred, _ = parse(ans)
            ok = pred != "invalid" and canon(pred) == canon(ex["label"])
            pin += len(prompt_ids); pout += len(toks)
            rows.append({"id": ex["id"], "text": ex["text"], "label": ex["label"], "raw": text, "pred": pred, "confidence": None,
                         "correct": ok, "latency": lat, "in_tokens": len(prompt_ids), "out_tokens": len(toks), "reasoning_tokens": 0,
                         "finish_reason": getattr(seq, "stop_reason", None) if seq else None, "error": None})
            print(("✓" if ok else "✗"), f"{ex['label'][:28]:28s} -> {pred[:28]:28s} {lat:.2f}s", flush=True)
    finally:
        sampler.close(); service.close()
    cost = (pin * PREFILL_RATE + pout * SAMPLE_RATE) / 1e6
    ledger_add(BASE + "-sft-sampler", pin, pout, cost, "sft_eval_sampler")
    n = len(rows); lats = sorted(r["latency"] for r in rows)
    summary = {"model": BASE + "-sft", "prompt": "v0_sft_short", "mock": False, "n": n, "seed": 0, "json_mode": False,
               "effort": "none", "accuracy": round(sum(r["correct"] for r in rows) / n, 4),
               "invalid_outputs": sum(r["pred"] == "invalid" for r in rows), "errors": 0,
               "p50_latency_s": round(statistics.median(lats), 3), "p95_latency_s": round(lats[int(0.95 * (n - 1))], 3),
               "cost_per_1k_requests_usd": round(cost / n * 1000, 4), "cost_total_usd": round(cost, 4),
               "in_tokens": pin, "out_tokens": pout, "reasoning_tokens": 0, "serving_note":
               "scored via serverless training sampler at training-API rates; serving would need a dedicated deployment (not created)",
               "rows": rows}
    out = os.path.join(HERE, "results", "muse-glimmer-30b_sft.json")
    json.dump(summary, open(out, "w"), indent=2)
    print(f"\nmuse-glimmer-30b SFT: acc {summary['accuracy']:.1%} invalid {summary['invalid_outputs']} p50 {summary['p50_latency_s']}s cost ${cost:.4f}; saved {out}")

if __name__ == "__main__":
    {"plan": cmd_plan, "train": cmd_train, "eval": cmd_eval}[sys.argv[1]]()
