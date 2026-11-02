#!/usr/bin/env python3
"""Free LoRA SFT of Muse Glimmer 30B on Fireworks Serverless Training, then score the checkpoint on the locked
test set by sampling (no deployment). Docs: docs.fireworks.ai/fine-tuning/training-api/serverless.md and
fine-tuning/models.md ("Muse Glimmer 30B SFT is free to train until November 30, 2026").

  .venv311/bin/python sft/train_sft.py prepare          # writes sft/train_chat.jsonl (run check_leak on it)
  .venv311/bin/python sft/train_sft.py plan             # offline: token stats, step count, expected eval cost
  .venv311/bin/python sft/train_sft.py train            # trains, saves sampler checkpoint path to sft/checkpoint.json
  .venv311/bin/python sft/train_sft.py eval             # samples the checkpoint on data/test.jsonl -> results/...json
Budget: training is covered by the promotion; sampling is billed (Muse Glimmer: $1.96/M prefill, $4.88/M sample).
"""
import csv, json, os, random, statistics, sys, time
from concurrent.futures import ThreadPoolExecutor

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)
import score  # noqa: E402

BASE_MODEL = "accounts/fireworks/models/muse-glimmer-30b"
TOKENIZER_DIR = os.path.join(HERE, "tokenizer")
SERVERLESS_URL = "https://api.fireworks.ai/training/v1/serverless"
PRICE_PREFILL, PRICE_SAMPLE = 1.96, 4.88  # $/M, Muse Glimmer 30B serverless training sampling (docs, 2026-11-01)
EPOCHS, BATCH, LR, RANK, MAX_SEQ = 3, 16, 1e-4, 8, 1024
SEED = 7
LABELS = [l["name"] for l in json.load(open(os.path.join(ROOT, "data", "labels.json")))["labels"]]
SYSTEM = ("Classify the contract clause into exactly one of these LEDGAR categories and reply with the category name only.\n"
          "Categories: " + "; ".join(LABELS))

def load_jsonl(p):
    return [json.loads(l) for l in open(p) if l.strip()]

def tokenizer():
    from transformers import AutoTokenizer
    return AutoTokenizer.from_pretrained(TOKENIZER_DIR)

def messages(text, label=None):
    m = [{"role": "system", "content": SYSTEM}, {"role": "user", "content": text}]
    if label is not None:
        m.append({"role": "assistant", "content": label})
    return m

def prepare():
    rows = load_jsonl(os.path.join(ROOT, "data", "train.jsonl"))
    out = os.path.join(HERE, "train_chat.jsonl")
    with open(out, "w") as f:
        for r in rows:
            f.write(json.dumps({"messages": messages(r["text"], r["label"])}) + "\n")
    print(f"wrote {out} ({len(rows)} rows). Now run: python3 ../common/check_leak.py data/test.jsonl sft/train_chat.jsonl")

def render(tok, msgs):
    """Returns (token ids, weights) with loss only on the assistant reply (incl. its <|eot|>)."""
    full = tok.apply_chat_template(msgs, tokenize=False)
    prompt = tok.apply_chat_template(msgs[:2], tokenize=False, add_generation_prompt=True)
    assert full.startswith(prompt)
    ids_p = tok.encode(prompt, add_special_tokens=False)
    ids = tok.encode(full, add_special_tokens=False)
    assert ids[: len(ids_p)] == ids_p, "prompt is not a token prefix of the full rendering"
    w = [0.0] * len(ids_p) + [1.0] * (len(ids) - len(ids_p))
    return ids, w

def datums(tok, chat_rows):
    from fireworks.training.sdk import Datum, ModelInput
    out = []
    for r in chat_rows:
        ids, w = render(tok, r["messages"])
        if len(ids) > MAX_SEQ:
            continue
        # right-shifted Tinker-style datum: predict token t+1 from tokens <= t
        out.append(Datum(model_input=ModelInput.from_ints(ids[:-1]),
                         loss_fn_inputs={"target_tokens": ids[1:], "weights": w[1:]}))
    return out

def plan():
    tok = tokenizer()
    rows = load_jsonl(os.path.join(HERE, "train_chat.jsonl"))
    lens = [len(render(tok, r["messages"])[0]) for r in rows]
    tr = sum(sum(render(tok, r["messages"])[1]) for r in rows)
    steps = EPOCHS * ((len(rows) + BATCH - 1) // BATCH)
    test = load_jsonl(os.path.join(ROOT, "data", "test.jsonl"))
    ptoks = sum(len(tok.encode(tok.apply_chat_template(messages(r["text"]), tokenize=False, add_generation_prompt=True), add_special_tokens=False)) for r in test)
    print(f"train rows {len(rows)}, seq len min/median/max {min(lens)}/{sorted(lens)[len(lens)//2]}/{max(lens)}, total tokens/epoch {sum(lens)}, loss tokens/epoch {int(tr)}")
    print(f"epochs {EPOCHS} batch {BATCH} -> {steps} optimizer steps, lr {LR}, rank {RANK}")
    print(f"eval: {len(test)} prompts, {ptoks} prefill tokens -> ~${ptoks*PRICE_PREFILL/1e6:.3f} prefill + ~${len(test)*16*PRICE_SAMPLE/1e6:.3f} sample (16 tok each)")
    print(f"system prompt tokens: {len(tok.encode(SYSTEM))}")

def ledger_add(ti, to, note):
    cost = (ti * PRICE_PREFILL + to * PRICE_SAMPLE) / 1e6
    with open(os.path.join(ROOT, "ledger.csv"), "a", newline="") as f:
        csv.writer(f).writerow([time.strftime("%Y-%m-%dT%H:%M:%S"), BASE_MODEL + "-lora(sampling)", ti, to, f"{cost:.6f}", note])
    return cost

def train():
    from fireworks.training.sdk import FiretitanServiceClient, AdamParams
    tok = tokenizer()
    rows = load_jsonl(os.path.join(HERE, "train_chat.jsonl"))
    data = datums(tok, rows)
    print(f"{len(data)} datums")
    service = FiretitanServiceClient(api_key=os.environ["FIREWORKS_API_KEY"], base_url=SERVERLESS_URL)
    tc = service.create_lora_training_client(base_model=BASE_MODEL, rank=RANK, alpha=16, seed=SEED)
    info = {"session": service.training_session_id, "session_name": getattr(service, "training_session_name", None), "run": tc.run_id, "started": time.strftime("%Y-%m-%dT%H:%M:%S")}
    print("session", info)
    json.dump(info, open(os.path.join(HERE, "session.json"), "w"), indent=1)
    rng = random.Random(SEED)
    mf = open(os.path.join(HERE, "metrics.jsonl"), "a")
    step, total = 0, EPOCHS * ((len(data) + BATCH - 1) // BATCH)
    for ep in range(EPOCHS):
        rng.shuffle(data)
        for i in range(0, len(data), BATCH):
            batch = data[i:i + BATCH]
            lr = LR * (1 - step / total) + 1e-6  # linear decay
            fb = tc.forward_backward(batch, "cross_entropy").result()
            tc.optim_step(AdamParams(learning_rate=lr, beta1=0.9, beta2=0.95, eps=1e-8, weight_decay=0.0)).result()
            m = getattr(fb, "metrics", {}) or {}
            loss_sum, resp = m.get("loss:sum"), m.get("response_tokens")
            mean = (loss_sum / max(resp, 1.0)) if loss_sum is not None and resp else getattr(fb, "loss", None)
            rec = {"step": step, "epoch": ep, "lr": lr, "mean_nll": mean, "loss_sum": loss_sum, "response_tokens": resp}
            mf.write(json.dumps(rec) + "\n"); mf.flush()
            print(f"step {step}/{total} ep {ep} lr {lr:.2e} mean_nll {mean}", flush=True)
            step += 1
        name = f"ep{ep + 1}"
        path = tc.save_weights_for_sampler(name).result().path
        print("saved sampler checkpoint", name, path)
        info[name] = path
        json.dump(info, open(os.path.join(HERE, "session.json"), "w"), indent=1)
    info["final"] = info[f"ep{EPOCHS}"]
    json.dump(info, open(os.path.join(HERE, "checkpoint.json"), "w"), indent=1)
    print("done; final checkpoint", info["final"])

def parse_reply(text):
    # Muse Glimmer answers on a channel: ' to=user<|message|>Notices<|eot|>' (possibly after a to=self reasoning channel)
    if "to=user<|message|>" in text:
        text = text.split("to=user<|message|>")[-1]
    elif "<|message|>" in text:
        text = text.split("<|message|>")[-1]
    for t in ("<|eot|>", "<|end_of_text|>", "<|start|>"):
        text = text.split(t)[0]
    return text.strip()

def evaluate(checkpoint=None, tag="v5_short", limit=0, workers=4):
    from fireworks.training.sdk import FiretitanServiceClient, ModelInput, SamplingParams
    tok = tokenizer()
    ck = checkpoint or json.load(open(os.path.join(HERE, "checkpoint.json")))["final"]
    test = load_jsonl(os.path.join(ROOT, "data", "test.jsonl"))
    random.Random(SEED).shuffle(test)
    if limit:
        test = test[:limit]
    service = FiretitanServiceClient(api_key=os.environ["FIREWORKS_API_KEY"], base_url=SERVERLESS_URL)
    sampler = service.create_sampling_client(model_path=ck, tokenizer=tok)
    eot = tok.encode("<|eot|>", add_special_tokens=False)
    params = SamplingParams(max_tokens=48, temperature=0.0, stop=eot)

    def one(ex):
        prompt_txt = tok.apply_chat_template(messages(ex["text"]), tokenize=False, add_generation_prompt=True)
        ids = tok.encode(prompt_txt, add_special_tokens=False)
        t0 = time.time()
        for attempt in range(4):
            try:
                res = sampler.sample(prompt=ModelInput.from_ints(ids), num_samples=1, sampling_params=params).result()
                break
            except Exception as e:
                if attempt == 3:
                    return {"id": ex["id"], "text": ex["text"], "label": ex["label"], "raw": "", "pred": "invalid", "correct": False,
                            "latency": time.time() - t0, "in_tokens": len(ids), "out_tokens": 0, "finish": f"error {e}"}
                time.sleep(2 ** attempt)
        lat = time.time() - t0
        seq = res.sequences[0]
        out_ids = list(seq.tokens or [])
        raw = tok.decode(out_ids, skip_special_tokens=False)
        pred = score.normalize(parse_reply(raw))
        ledger_add(len(ids), len(out_ids), f"sft-eval-{tag}")
        row = {"id": ex["id"], "text": ex["text"], "label": ex["label"], "raw": raw[:2000], "pred": pred, "correct": pred == ex["label"],
               "latency": round(lat, 3), "in_tokens": len(ids), "out_tokens": len(out_ids), "finish": str(getattr(seq, "stop_reason", ""))}
        print(("✓" if row["correct"] else "✗"), f"{ex['label']:28s} -> {pred:28s} {lat:.2f}s out={len(out_ids)} {raw[:40]!r}", flush=True)
        return row

    try:
        with ThreadPoolExecutor(max_workers=workers) as pool:
            rows = list(pool.map(one, test))
    finally:
        sampler.close()
    m = score.metrics(rows)
    lat = sorted(r["latency"] for r in rows)
    ti, to = sum(r["in_tokens"] for r in rows), sum(r["out_tokens"] for r in rows)
    cost = (ti * PRICE_PREFILL + to * PRICE_SAMPLE) / 1e6
    summary = {"model": BASE_MODEL + "-lora", "prompt": tag, "tag": "sft", "seed": SEED, "fewshot": 0, "json_mode": False, "mock": False,
               "n": m["n"], "accuracy": m["accuracy"], "macro_f1": m["macro_f1"], "invalid_outputs": m["invalid"],
               "p50_latency_s": round(statistics.median(lat), 3), "p95_latency_s": round(lat[int(0.95 * (len(lat) - 1))], 3),
               "in_tokens": ti, "out_tokens": to, "cost_usd": round(cost, 4), "cost_per_1k_requests_usd": round(cost / m["n"] * 1000, 4),
               "checkpoint": ck, "pricing_note": "serverless-training sampling rates (prefill 1.96, sample 4.88 $/M); production serving would need a dedicated deployment",
               "rows": rows}
    out = os.path.join(ROOT, "results", f"muse-glimmer-30b-lora_{tag}_sft_s{SEED}.json")
    json.dump(summary, open(out, "w"), indent=1)
    print(f"\nSFT eval: acc {m['accuracy']:.1%} | macroF1 {m['macro_f1']:.3f} | invalid {m['invalid']} | p50 {summary['p50_latency_s']}s | ${summary['cost_per_1k_requests_usd']:.3f}/1k | cost ${cost:.3f}")
    print("saved", out)

def cleanup():
    """Delete the training session to free the account's single Muse Glimmer slot (run after eval)."""
    import urllib.request
    info = json.load(open(os.path.join(HERE, "session.json")))
    name = info.get("session_name")
    if not name:
        sys.exit("no session_name recorded")
    req = urllib.request.Request(f"https://api.fireworks.ai/v1/{name}", method="DELETE",
                                 headers={"Authorization": f"Bearer {os.environ['FIREWORKS_API_KEY']}"})
    with urllib.request.urlopen(req, timeout=60) as r:
        print("deleted", name, r.status)

if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "plan"
    {"prepare": prepare, "plan": plan, "train": train, "cleanup": cleanup}.get(cmd, lambda: evaluate(*(sys.argv[2:3] or [None])))()
