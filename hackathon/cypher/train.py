"""LoRA SFT of Muse Glimmer 30B on the Fireworks Serverless Training API. Adapted from ../submission/train/tune.py.

  python train.py plan    --data data/sft_ft1_gold.jsonl                 # token counts, no network
  python train.py sft     --data data/sft_ft1_gold.jsonl --tag ft1        # train; prints the sampler checkpoint
  python train.py cleanup --tag ft1                                      # delete the session (frees a run slot)

Evaluate a checkpoint with: python run_eval.py --model muse-glimmer-30b --model-path <checkpoint> ...

Cost: Muse Glimmer 30B LoRA SFT is free until 2026-11-30 (docs.fireworks.ai/fine-tuning/models; checked by
../submission/train/tune.py). This script refuses to train after that. Sampling is paid and goes through fw.py.
Prompts are tokenized exactly as fw.TrainingSampler tokenizes them at test time, including the answer prefill.
"""
import argparse, json, os, random, time
from datetime import datetime, timedelta, timezone

import fw
from run_eval import load_env, load_jsonl

HERE = os.path.dirname(os.path.abspath(__file__))
SESSIONS = os.path.join(HERE, "results", "train")
FREE_UNTIL = datetime(2026, 12, 1, tzinfo=timezone(timedelta(hours=-8)))  # end of 2026-11-30, Pacific
SEED = 0


def tokenizer_and_prefill():
    """The sampler's tokenizer and render functions, without opening a sampling connection."""
    s = fw.TrainingSampler.__new__(fw.TrainingSampler)
    from transformers import AutoTokenizer
    s.tok = AutoTokenizer.from_pretrained(fw.MUSE_TOKENIZER)
    s.prefill = s._answer_prefill()
    return s


def build_datums(s, examples):
    """Loss only on the answer tokens (and the end-of-turn token after them)."""
    from fireworks.training import sdk
    datums, n_tokens = [], 0
    for e in examples:
        prompt = s.prompt_ids(e["messages"])
        full = s._render(e["messages"] + [{"role": "assistant", "content": e["answer"]}], False)
        assert full[: len(prompt)] == prompt, f"{e['id']}: training prompt differs from the test-time prompt"
        weights = [0.0] * (len(prompt) - 1) + [1.0] * (len(full) - len(prompt))
        datums.append(sdk.Datum(
            model_input=sdk.ModelInput.from_ints(full[:-1]),
            loss_fn_inputs={"target_tokens": sdk.TensorData(data=full[1:], dtype="int64", shape=[len(full) - 1]),
                            "weights": sdk.TensorData(data=weights, dtype="float32", shape=[len(weights)])}))
        n_tokens += len(full)
    return datums, n_tokens


def plan(args):
    s = tokenizer_and_prefill()
    examples = load_jsonl(args.data)
    _, n = build_datums(s, examples)
    print(f"{len(examples)} examples, {n} tokens/epoch, {args.epochs} epochs -> {n * args.epochs} training tokens")


def sft(args):
    from fireworks.training import sdk
    from fireworks.training.sdk import FiretitanServiceClient
    if datetime.now(timezone.utc) >= FREE_UNTIL:
        raise SystemExit("free Muse Glimmer SFT has ended; re-check pricing before training")
    s = tokenizer_and_prefill()
    examples = load_jsonl(args.data)
    datums, n_tokens = build_datums(s, examples)
    service = FiretitanServiceClient(api_key=os.environ["FIREWORKS_API_KEY"], base_url=fw.TRAINING_URL)
    for attempt in range(60):  # the account allows one Muse run at a time: wait for the slot instead of failing
        try:
            tc = service.create_lora_training_client(base_model=fw.MUSE, rank=args.rank, alpha=2 * args.rank, seed=SEED)
            break
        except Exception as e:
            if "concurrent" not in str(e) or attempt == 59:
                raise
            print("training slot busy, retrying in 30 s", flush=True)
            time.sleep(30)
    os.makedirs(SESSIONS, exist_ok=True)
    info_path = os.path.join(SESSIONS, f"{args.tag}.json")
    info = {"tag": args.tag, "data": args.data, "examples": len(datums), "tokens_per_epoch": n_tokens,
            "session_name": getattr(service, "training_session_name", None), "run": tc.run_id,
            "epochs": args.epochs, "batch": args.batch, "lr": args.lr, "rank": args.rank,
            "started": time.strftime("%Y-%m-%dT%H:%M:%S"), "log": []}
    json.dump(info, open(info_path, "w"), indent=1)  # saved early so cleanup works even if training dies
    print(f"session {info['session_name']}  {len(datums)} examples, {n_tokens} tokens/epoch", flush=True)

    rng, step = random.Random(SEED), 0
    total = args.epochs * -(-len(datums) // args.batch)
    for epoch in range(args.epochs):
        order = list(range(len(datums)))
        rng.shuffle(order)
        for i in range(0, len(order), args.batch):
            lr = args.lr * max(0.1, 1 - step / total)  # linear decay to 10%
            fb = tc.forward_backward([datums[j] for j in order[i: i + args.batch]], "cross_entropy").result()
            tc.optim_step(sdk.AdamParams(learning_rate=lr)).result()
            m = getattr(fb, "metrics", None) or {}
            nll = m["loss:sum"] / max(m["response_tokens"], 1.0) if m.get("loss:sum") is not None and m.get("response_tokens") else None
            step += 1
            info["log"].append({"step": step, "epoch": epoch, "lr": lr, "mean_nll": nll})
            print(f"step {step}/{total}  epoch {epoch}  lr {lr:.2e}  mean_nll {nll}", flush=True)
        json.dump(info, open(info_path, "w"), indent=1)

    info["checkpoint"] = tc.save_weights_for_sampler(f"{args.tag}-{int(time.time()) % 100000}").result().path
    info["finished"] = time.strftime("%Y-%m-%dT%H:%M:%S")
    json.dump(info, open(info_path, "w"), indent=1)
    print("checkpoint:", info["checkpoint"], flush=True)


def cleanup(args):
    import urllib.request
    name = json.load(open(os.path.join(SESSIONS, f"{args.tag}.json")))["session_name"]
    req = urllib.request.Request(f"https://api.fireworks.ai/v1/{name}", method="DELETE",
                                 headers={"Authorization": f"Bearer {os.environ['FIREWORKS_API_KEY']}"})
    with urllib.request.urlopen(req, timeout=60) as r:
        print("deleted", name, r.status)


def main():
    ap = argparse.ArgumentParser()
    sp = ap.add_subparsers(dest="cmd", required=True)
    for name in ("plan", "sft"):
        p = sp.add_parser(name)
        p.add_argument("--data", required=True)
        p.add_argument("--tag", default="plan")
        p.add_argument("--epochs", type=int, default=2)
        p.add_argument("--batch", type=int, default=16)
        p.add_argument("--rank", type=int, default=16)
        p.add_argument("--lr", type=float, default=1e-4)
    sp.add_parser("cleanup").add_argument("--tag", required=True)
    args = ap.parse_args()
    load_env()
    {"plan": plan, "sft": sft, "cleanup": cleanup}[args.cmd](args)


if __name__ == "__main__":
    main()
