#!/usr/bin/env python3
"""Free LoRA SFT of Muse Glimmer 30B on the Fireworks Serverless Training API, then score base and tuned
checkpoints on data/test.jsonl via serverless checkpoint sampling (no deployment).
Promotion evidence: docs/fine-tuning/models.md and cookbook/muse-glimmer.md say Muse Glimmer 30B LoRA SFT is $0 until 2026-11-30.
Sampling (prefill $1.96/M, sample $4.88/M) is NOT covered and is logged to ../ledger.csv.
Run from this folder with the 3.11 venv:  ./venv/bin/python sft_muse.py --train ../data/train.jsonl --test ../data/test.jsonl
"""
import argparse, csv, json, os, statistics, sys, time
from datetime import datetime
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
import score as sc

BASE = "accounts/fireworks/models/muse-glimmer-30b"
TOK = "meta-models/Muse-Glimmer-30B"
EOT = 200008
SAMPLE_PRICE = (1.96, 4.88)  # $/M prefill, sample
LEDGER = os.path.join(os.path.dirname(HERE), "ledger.csv")


def ledger(note, in_tok, out_tok, cost):
    with open(LEDGER, "a", newline="") as f:
        csv.writer(f).writerow([datetime.now().isoformat(timespec="seconds"), "muse-glimmer-30b-sampler", in_tok, out_tok, f"{cost:.6f}", note])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--train", default=os.path.join(os.path.dirname(HERE), "data", "train.jsonl"))
    ap.add_argument("--test", default=os.path.join(os.path.dirname(HERE), "data", "test.jsonl"))
    ap.add_argument("--prompt", default=os.path.join(os.path.dirname(HERE), "prompts", "v2_rubric.txt"))
    ap.add_argument("--epochs", type=int, default=2)
    ap.add_argument("--batch", type=int, default=16)
    ap.add_argument("--lr", type=float, default=1e-4)
    ap.add_argument("--rank", type=int, default=8)
    ap.add_argument("--base-limit", type=int, default=100, help="rows for the base-model eval (sampling is paid)")
    ap.add_argument("--tuned-limit", type=int, default=0)
    ap.add_argument("--max-tokens", type=int, default=400)
    ap.add_argument("--base-max-tokens", type=int, default=1500)
    ap.add_argument("--skip-base", action="store_true")
    ap.add_argument("--out", default=os.path.join(os.path.dirname(HERE), "results"))
    a = ap.parse_args()

    from transformers import AutoTokenizer
    from fireworks.training.sdk import FiretitanServiceClient, AdamParams, types
    tok = AutoTokenizer.from_pretrained(TOK)
    system = open(a.prompt).read()

    def prompt_ids(text):
        txt = tok.apply_chat_template([{"role": "system", "content": system}, {"role": "user", "content": text}], tokenize=False, add_generation_prompt=True, reasoning_strength="low")
        return tok.encode(txt, add_special_tokens=False)

    def datum(row):
        p = list(prompt_ids(row["text"]))
        c = tok.encode(" to=user<|message|>" + json.dumps(row["gold"]) + "<|eot|>", add_special_tokens=False)
        toks = p + c; w = [0.0] * len(p) + [1.0] * len(c)
        d = types.Datum(model_input=types.ModelInput.from_ints(toks[:-1]), loss_fn_inputs={"target_tokens": toks[1:], "weights": w[1:]})
        return d

    train = [json.loads(l) for l in open(a.train) if l.strip()]
    test = [json.loads(l) for l in open(a.test) if l.strip()]
    datums = [datum(r) for r in train]
    n_train_tok = sum(len(d.model_input.to_ints()) for d in datums)
    print(f"{len(datums)} train datums, {n_train_tok} tokens (training meter; promo says $0, list rate would be ${n_train_tok*5.86/1e6*a.epochs:.2f})", flush=True)

    service = FiretitanServiceClient(api_key=os.environ["FIREWORKS_API_KEY"], base_url="https://api.fireworks.ai/training/v1/serverless")
    tc = service.create_lora_training_client(base_model=BASE, rank=a.rank, alpha=32)
    print(f"session={service.training_session_id} run={tc.run_id}", flush=True)
    log = open(os.path.join(HERE, "sft_metrics.jsonl"), "a")

    def evaluate(label, rows, max_tokens):
        snap = tc.save_weights_for_sampler(f"pj-{label}").result().path
        print(f"{label}: snapshot {snap}", flush=True)
        sampler = service.create_sampling_client(model_path=snap, tokenizer=tok)
        params = types.SamplingParams(max_tokens=max_tokens, temperature=0.0, stop=[EOT])
        out, in_tok, out_tok = [], 0, 0
        try:
            prompts = [types.ModelInput.from_ints(list(prompt_ids(r["text"]))) for r in rows]
            t0 = time.time()
            futs = [sampler.sample(prompt=p, num_samples=1, sampling_params=params) for p in prompts]
            for i, (r, p, f) in enumerate(zip(rows, prompts, futs)):
                t1 = time.time(); res = f.result(); lat = time.time() - t1
                seq = res.sequences[0]; toks = list(seq.tokens)
                in_tok += len(p.to_ints()); out_tok += len(toks)
                text = tok.decode(toks)
                # keep only the final user-facing segment
                if "to=user<|message|>" in text:
                    text = text.split("to=user<|message|>")[-1]
                text = text.split("<|eot|>")[0].split("<|eom|>")[0]
                s = sc.score(text, r["gold"])
                out.append({"id": r["id"], "text": r["text"], "gold": r["gold"], "raw": tok.decode(toks)[:3000], "pred": s["parsed"], "valid": s["valid"], "problems": s["problems"],
                            "fields": s["fields"], "correct": s["all_correct"], "n_correct": s["n_correct"], "latency": lat, "in_tok": len(p.to_ints()), "out_tok": len(toks), "finish": str(seq.stop_reason)})
                if (i + 1) % 20 == 0: print(f"{label}: {i+1}/{len(rows)} acc so far {sum(o['correct'] for o in out)/(i+1):.1%}", flush=True)
        finally:
            sampler.close()
        cost = (in_tok * SAMPLE_PRICE[0] + out_tok * SAMPLE_PRICE[1]) / 1e6
        ledger(f"sft-eval-{label}", in_tok, out_tok, cost)
        n = len(out); lat = sorted(o["latency"] for o in out)
        summ = {"model": f"muse-glimmer-30b-{label}", "prompt": "v2_rubric_sft" if label == "tuned" else "v2_rubric", "json_mode": False, "seed": 7, "mock": False, "n": n,
                "accuracy": round(sum(o["correct"] for o in out) / n, 4), "mean_field_accuracy": round(sum(o["n_correct"] for o in out) / (8 * n), 4),
                "field_accuracy": {k: round(sum(o["fields"][k] for o in out) / n, 4) for k in sc.FIELDS}, "invalid_outputs": sum(not o["valid"] for o in out),
                "p50_latency_s": round(statistics.median(lat), 3), "p95_latency_s": round(lat[int(0.95 * (n - 1))], 3), "in_tokens": in_tok, "out_tokens": out_tok,
                "cost_usd": round(cost, 4), "cost_per_1k_requests_usd": round(cost / n * 1000, 4), "note": "sampler pricing (serverless training meters), not serverless inference pricing; serving needs an on-demand deployment", "rows": out}
        path = os.path.join(a.out, f"muse-glimmer-30b_{label}_s7.json"); json.dump(summ, open(path, "w"), indent=1)
        print(f"{label}: acc {summ['accuracy']:.1%} field-mean {summ['mean_field_accuracy']:.1%} invalid {summ['invalid_outputs']} p50 {summ['p50_latency_s']}s cost ${cost:.3f} -> {path}", flush=True)
        return summ

    if not a.skip_base:
        evaluate("base", test[: a.base_limit] if a.base_limit else test, a.base_max_tokens)

    adam = AdamParams(learning_rate=a.lr, beta1=0.9, beta2=0.95, eps=1e-8, weight_decay=0.0)
    step = 0
    for ep in range(a.epochs):
        import random; random.Random(ep).shuffle(datums)
        for i in range(0, len(datums), a.batch):
            batch = datums[i:i + a.batch]
            fb = tc.forward_backward(batch, "cross_entropy").result()
            opt = tc.optim_step(adam).result()
            step += 1
            loss = fb.metrics.get("loss:sum", 0) / max(fb.metrics.get("response_tokens", 1), 1)
            rec = {"epoch": ep, "step": step, "loss": loss, "metrics": {k: float(v) for k, v in fb.metrics.items()}}
            log.write(json.dumps(rec) + "\n"); log.flush()
            print(f"epoch {ep} step {step} loss {loss:.4f}", flush=True)
    evaluate("tuned", test[: a.tuned_limit] if a.tuned_limit else test, a.max_tokens)
    try:
        import urllib.request
        req = urllib.request.Request(f"https://api.fireworks.ai/v1/accounts/raheeldeal/trainingSessions/{service.training_session_id}", method="DELETE", headers={"Authorization": f"Bearer {os.environ['FIREWORKS_API_KEY']}"})
        print("session delete:", urllib.request.urlopen(req, timeout=30).status)
    except Exception as e:
        print("session delete failed (slot frees on its own):", e)


if __name__ == "__main__":
    main()
