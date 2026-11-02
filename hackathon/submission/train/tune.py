#!/usr/bin/env python3
"""Catalog-free tool routing on Muse Glimmer 30B: SFT + RFT (rejection sampling) via the Fireworks Serverless Training API.

No dataset upload, no deployment. Training on Muse Glimmer 30B is free until 2026-11-30 (docs.fireworks.ai/fine-tuning/models.md);
sampling from the training pool is billed per token (prefill $1.96/M, sample $4.88/M) and logged to ledger.csv.

  PY=../../runs/regex/venv311/bin/python            # Python 3.11 + fireworks-ai[training] + transformers
  $PY tune.py plan    --data ../data/train.jsonl                       # offline token counts
  $PY tune.py eval    --model base --out results/base_nocatalog.json   # untuned base, bare request
  $PY tune.py train   --data ../data/train.jsonl --tag sft             # LoRA SFT -> results/sft_session.json
  $PY tune.py eval    --model <checkpoint> --out results/sft_nocatalog.json
  $PY tune.py sample  --model <checkpoint> --data ../data/train.jsonl --n 4 --temp 0.8 --out results/rft1_candidates.jsonl
  $PY tune.py select  --candidates results/rft1_candidates.jsonl --out data/rft_round1.jsonl
  $PY tune.py cleanup --session results/sft_session.json               # DELETE the training session (frees the account's one slot)

Prompt at train and test time: system "Reply with the single best tool name." + the bare user request. No catalog.
"""
import argparse, csv, json, os, random, statistics, sys, time
from concurrent.futures import ThreadPoolExecutor

HERE = os.path.dirname(os.path.abspath(__file__))
SUB = os.path.dirname(HERE)
sys.path.insert(0, SUB)
import score  # noqa: E402  (submission/score.py)

BASE_MODEL = "accounts/fireworks/models/muse-glimmer-30b"
TOKENIZER = "meta-models/Muse-Glimmer-30B"
TOKENIZER_FALLBACK = os.path.join(SUB, "..", "runs", "legal-clauses", "sft", "tokenizer")
SERVERLESS_URL = "https://api.fireworks.ai/training/v1/serverless"
PRICE_PREFILL, PRICE_SAMPLE = 1.96, 4.88  # $/M tokens, Muse Glimmer 30B serverless-training sampling (docs 2026-11-01)
CAP = 3.00
SYSTEM = "Reply with the single best tool name."
LEDGER = os.path.join(HERE, "ledger.csv")
SEED = 0


# ---------- helpers ----------
def load_jsonl(p):
    return [json.loads(l) for l in open(p) if l.strip()]


def ledger_total():
    if not os.path.exists(LEDGER):
        return 0.0
    return sum(float(r["cost"]) for r in csv.DictReader(open(LEDGER)))


def ledger_add(model, tin, tout, note):
    cost = (tin * PRICE_PREFILL + tout * PRICE_SAMPLE) / 1e6
    new = not os.path.exists(LEDGER)
    with open(LEDGER, "a", newline="") as f:
        w = csv.writer(f)
        if new:
            w.writerow(["timestamp", "model", "in_tokens", "out_tokens", "cost", "note"])
        w.writerow([time.strftime("%Y-%m-%dT%H:%M:%S"), model, tin, tout, f"{cost:.6f}", note])
    return cost


def get_tokenizer():
    from transformers import AutoTokenizer
    try:
        return AutoTokenizer.from_pretrained(TOKENIZER)
    except Exception as e:  # offline fallback: same files, downloaded last night
        print("hub tokenizer failed, using local copy:", e)
        return AutoTokenizer.from_pretrained(TOKENIZER_FALLBACK)


def _ids(tok, text):
    return list(tok(text, add_special_tokens=False)["input_ids"])


def render(tok, user, assistant=None):
    """(prompt_ids, full_ids). reasoning_strength=low so the model answers on the user channel directly."""
    msgs = [{"role": "system", "content": SYSTEM}, {"role": "user", "content": user}]
    prompt = _ids(tok, tok.apply_chat_template(msgs, tokenize=False, add_generation_prompt=True, reasoning_strength="low"))
    if assistant is None:
        return prompt, None
    full = _ids(tok, tok.apply_chat_template(msgs + [{"role": "assistant", "content": assistant}], tokenize=False, reasoning_strength="low"))
    assert full[: len(prompt)] == prompt, "chat template prefix mismatch"
    return prompt, full


def answer_prefill(tok):
    """Muse answers as '<|start|>assistant to=user<|message|>ANSWER<|eot|>'. Left alone the base model opens a to=self
    reasoning channel and burns the budget; prefilling ' to=user<|message|>' forces a direct answer. Base, SFT and RFT
    are all sampled with the same prefill, so deltas are attributable to the weights."""
    msg_id = tok.convert_tokens_to_ids("<|message|>")
    p, full = render(tok, "probe", "x")
    return full[len(p): len(full) - full[::-1].index(msg_id)]


def parse_reply(text):
    if "<|message|>" in text:
        text = text.split("<|message|>")[-1]
    for t in ("<|eot|>", "<|end_of_text|>", "<|start|>"):
        text = text.split(t)[0]
    return text.strip()


def service_client():
    from fireworks.training.sdk import FiretitanServiceClient
    return FiretitanServiceClient(api_key=os.environ["FIREWORKS_API_KEY"], base_url=SERVERLESS_URL)


def make_sampler(service, tok, model):
    if model == "base":
        return service.create_sampling_client(base_model=BASE_MODEL, tokenizer=tok)
    return service.create_sampling_client(model_path=model, tokenizer=tok)


# ---------- training ----------
def build_datums(tok, rows):
    from fireworks.training import sdk
    datums, n_tok, n_train = [], 0, 0
    for r in rows:
        prompt, full = render(tok, r["text"], r["label"])
        weights = [0.0] * (len(prompt) - 1) + [1.0] * (len(full) - len(prompt))
        datums.append(sdk.Datum(
            model_input=sdk.ModelInput.from_ints(full[:-1]),
            loss_fn_inputs={"target_tokens": sdk.TensorData(data=full[1:], dtype="int64", shape=[len(full) - 1]),
                            "weights": sdk.TensorData(data=weights, dtype="float32", shape=[len(weights)])}))
        n_tok += len(full)
        n_train += int(sum(weights))
    return datums, n_tok, n_train


def plan(args):
    tok = get_tokenizer()
    rows = load_jsonl(args.data)
    _, n_tok, n_train = build_datums(tok, rows)
    test = load_jsonl(os.path.join(SUB, "data", "test.jsonl"))
    ptoks = sum(len(render(tok, r["text"])[0]) for r in test)
    print(f"{len(rows)} rows, {n_tok} tokens/epoch ({n_train} loss tokens), epochs {args.epochs} -> {n_tok * args.epochs} training tokens (free)")
    print(f"eval: {len(test)} prompts, {ptoks} prefill tokens (~{ptoks / len(test):.0f}/call) -> ~${ptoks * PRICE_PREFILL / 1e6:.3f} + sample")
    print(f"prefill tokens: {tok.decode(answer_prefill(tok))!r}; ledger total ${ledger_total():.3f}")


def train(args):
    from fireworks.training import sdk
    tok = get_tokenizer()
    rows = load_jsonl(args.data)
    datums, n_tok, n_train = build_datums(tok, rows)
    print(f"{len(datums)} datums, {n_tok} tokens/epoch, {n_train} loss tokens/epoch, epochs {args.epochs}")
    service = service_client()
    for attempt in range(args.slot_retries + 1):
        try:
            tc = service.create_lora_training_client(base_model=BASE_MODEL, rank=args.rank, alpha=2 * args.rank, seed=SEED)
            break
        except Exception as e:
            if "concurrent" not in str(e) or attempt == args.slot_retries:
                raise
            print(f"slot busy ({str(e)[:80]}), retry in 60s", flush=True)
            time.sleep(60)
    info = {"session": service.training_session_id, "session_name": getattr(service, "training_session_name", None),
            "run": tc.run_id, "started": time.strftime("%Y-%m-%dT%H:%M:%S"), "tag": args.tag, "data": args.data,
            "rows": len(datums), "tokens_per_epoch": n_tok, "loss_tokens_per_epoch": n_train,
            "epochs": args.epochs, "batch": args.batch, "lr": args.lr, "rank": args.rank, "log": []}
    sess_path = os.path.join(HERE, "results", f"{args.tag}_session.json")
    json.dump(info, open(sess_path, "w"), indent=1)
    print("session", info["session_name"], "run", info["run"], flush=True)
    rng = random.Random(SEED)
    step, total = 0, args.epochs * ((len(datums) + args.batch - 1) // args.batch)
    for ep in range(args.epochs):
        order = list(range(len(datums)))
        rng.shuffle(order)
        for i in range(0, len(order), args.batch):
            batch = [datums[j] for j in order[i:i + args.batch]]
            lr = args.lr * max(0.1, 1 - step / total)
            fb = tc.forward_backward(batch, "cross_entropy").result()
            tc.optim_step(sdk.AdamParams(learning_rate=lr)).result()
            m = getattr(fb, "metrics", None) or {}
            loss_sum, resp = m.get("loss:sum"), m.get("response_tokens")
            mean = (loss_sum / max(resp, 1.0)) if loss_sum is not None and resp else None
            step += 1
            info["log"].append({"step": step, "epoch": ep, "lr": lr, "mean_nll": mean, "loss_sum": loss_sum, "response_tokens": resp})
            print(f"step {step}/{total} ep {ep} lr {lr:.2e} mean_nll {mean}", flush=True)
        json.dump(info, open(sess_path, "w"), indent=1)
    name = f"{args.tag}-{int(time.time())}"
    path = tc.save_weights_for_sampler(name).result().path
    info["checkpoint"] = path
    json.dump(info, open(sess_path, "w"), indent=1)
    ledger_add(BASE_MODEL + " (serverless training)", 0, 0, f"{args.tag} train {n_tok * args.epochs} tokens, free promo")
    print("checkpoint:", path, "\nsession file:", sess_path, flush=True)
    service.close()


# ---------- sampling ----------
def sample_rows(tok, sampler, rows, n, temp, max_tokens, note, workers=4):
    """Yield one record per row with n candidate completions. Prefill forces the user channel."""
    from fireworks.training import sdk
    prefill = answer_prefill(tok)
    eot = tok.convert_tokens_to_ids("<|eot|>")
    params = sdk.SamplingParams(max_tokens=max_tokens, temperature=temp, stop=[eot], seed=SEED if temp > 0 else None)

    def one(r):
        if ledger_total() >= CAP:
            raise RuntimeError(f"ledger ${ledger_total():.2f} >= cap ${CAP}")
        prompt = render(tok, r["text"])[0] + prefill
        t0, res = time.time(), None
        for attempt in range(5):
            try:
                res = sampler.sample(prompt=sdk.ModelInput.from_ints(prompt), num_samples=n, sampling_params=params).result()
                break
            except Exception as e:
                if attempt == 4:
                    print("ERROR", r["id"], e, flush=True)
                    return {"id": r["id"], "text": r["text"], "label": r["label"], "in_tokens": len(prompt), "latency": time.time() - t0,
                            "cands": [], "error": str(e)[:200]}
                time.sleep(2 ** attempt)
        lat = time.time() - t0
        cands = []
        for seq in (res.sequences or []):
            toks = list(seq.tokens or [])
            raw = tok.decode(toks, skip_special_tokens=False)
            n_out = len([t for t in toks if t != eot])
            cands.append({"raw": raw, "text": parse_reply(raw), "out_tokens": n_out, "stop": str(getattr(seq, "stop_reason", ""))})
        ledger_add(BASE_MODEL + " (sampler)", len(prompt), sum(c["out_tokens"] + 1 for c in cands), note)
        return {"id": r["id"], "text": r["text"], "label": r["label"], "in_tokens": len(prompt), "latency": round(lat, 3), "cands": cands}

    with ThreadPoolExecutor(max_workers=workers) as pool:
        return list(pool.map(one, rows))


def evaluate(args):
    tok = get_tokenizer()
    rows = load_jsonl(os.path.join(SUB, "data", "test.jsonl"))
    if args.limit:
        rows = rows[: args.limit]
    service = service_client()
    sampler = make_sampler(service, tok, args.model)
    label = os.path.splitext(os.path.basename(args.out))[0]
    try:
        recs = sample_rows(tok, sampler, rows, 1, 0.0, args.max_tokens, f"eval {label}", workers=args.workers)
    finally:
        sampler.close(); service.close()
    out_rows = []
    for rec in recs:
        c = rec["cands"][0] if rec["cands"] else {"raw": "", "text": "", "out_tokens": 0, "stop": "error"}
        s = score.score(c["text"], rec["label"])
        out_rows.append({"id": rec["id"], "text": rec["text"], "gold": rec["label"], "raw": c["raw"][:500], "pred": s["pred"],
                         "correct": s["top1"], "invalid": s["invalid"], "latency": rec["latency"], "in_tokens": rec["in_tokens"],
                         "out_tokens": c["out_tokens"], "finish_reason": c["stop"], "error": rec.get("error")})
        print(("✓" if s["top1"] else "✗"), f"{rec['label']:28s} -> {s['pred']:28s} out={c['out_tokens']} {rec['latency']:.2f}s", flush=True)
    n = len(out_rows)
    lat = sorted(r["latency"] for r in out_rows)
    ti, to = sum(r["in_tokens"] for r in out_rows), sum(r["out_tokens"] for r in out_rows)
    cost = (ti * PRICE_PREFILL + to * PRICE_SAMPLE) / 1e6
    summary = {"model": BASE_MODEL if args.model == "base" else f"{BASE_MODEL} + LoRA {args.model}", "prompt": "bare_request",
               "system_prompt": SYSTEM, "catalog_in_prompt": False, "n": n,
               "accuracy": round(sum(r["correct"] for r in out_rows) / n, 4),
               "invalid_outputs": sum(r["invalid"] for r in out_rows), "errors": sum(1 for r in out_rows if r.get("error")),
               "p50_latency_s": round(statistics.median(lat), 3), "p95_latency_s": round(lat[int(0.95 * (n - 1))], 3),
               "cost_per_1k_requests_usd": round(cost / n * 1000, 4), "in_tokens": ti, "out_tokens": to,
               "in_tokens_per_call": round(ti / n, 1), "out_tokens_per_call": round(to / n, 2), "cost_usd": round(cost, 5),
               "seed": SEED, "temperature": 0, "max_tokens": args.max_tokens, "checkpoint": args.model,
               "pricing_note": "serverless-training sampler rates (prefill $1.96/M, sample $4.88/M), not serverless inference pricing; "
                               "production serving of the LoRA needs a dedicated deployment (see DEPLOY.md)",
               "rows": out_rows}
    os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
    json.dump(summary, open(args.out, "w"), indent=1, ensure_ascii=False)
    print(f"\n{label}: acc {summary['accuracy']:.1%} | invalid {summary['invalid_outputs']} | errors {summary['errors']} | "
          f"p50 {summary['p50_latency_s']}s p95 {summary['p95_latency_s']}s | in {summary['in_tokens_per_call']} out {summary['out_tokens_per_call']} tok/call | "
          f"${summary['cost_per_1k_requests_usd']:.3f}/1k | cost ${cost:.4f} | ledger ${ledger_total():.3f}\nsaved {args.out}")


def sample(args):
    tok = get_tokenizer()
    rows = load_jsonl(args.data)
    if args.limit:
        rows = rows[: args.limit]
    service = service_client()
    sampler = make_sampler(service, tok, args.model)
    try:
        recs = sample_rows(tok, sampler, rows, args.n, args.temp, args.max_tokens, f"rft sample {os.path.basename(args.out)}", workers=args.workers)
    finally:
        sampler.close(); service.close()
    with open(args.out, "w") as f:
        for r in recs:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    hit = sum(any(score.score(c["text"], r["label"])["top1"] for c in r["cands"]) for r in recs)
    print(f"sampled {len(recs)} prompts x {args.n}; prompts with >=1 correct candidate: {hit}/{len(recs)}; ledger ${ledger_total():.3f}\nsaved {args.out}")


# ---------- RFT reward + selection ----------
def reward(cand_text, out_tokens, gold):
    """1.0 if the predicted tool is the gold tool else 0.0, times 1.0 if the output is <= 8 tokens else 0.5.
    (The length factor only matters when correct; a wrong answer is 0 regardless.)"""
    correct = score.score(cand_text, gold)["top1"]
    length_factor = 1.0 if out_tokens <= 8 else 0.5
    return (1.0 if correct else 0.0) * length_factor


def select(args):
    recs = load_jsonl(args.candidates)
    kept, dropped, stats = [], 0, {"r1": 0, "r0.5": 0, "r0": 0}
    for r in recs:
        best = None
        for c in r["cands"]:
            rw = reward(c["text"], c["out_tokens"], r["label"])
            key = (rw, -c["out_tokens"])  # ties -> shortest
            if best is None or key > best[0]:
                best = (key, c, rw)
        if best is None or best[2] <= 0:
            dropped += 1          # no correct candidate: nothing to imitate (no gold injection; this is on-policy data only)
            stats["r0"] += 1
            continue
        stats["r1" if best[2] == 1.0 else "r0.5"] += 1
        kept.append({"id": r["id"], "text": r["text"], "label": best[1]["text"].strip(), "gold": r["label"], "reward": best[2],
                     "out_tokens": best[1]["out_tokens"]})
    with open(args.out, "w") as f:
        for k in kept:
            f.write(json.dumps(k, ensure_ascii=False) + "\n")
    print(f"kept {len(kept)}/{len(recs)} prompts (reward 1.0: {stats['r1']}, 0.5: {stats['r0.5']}); dropped {dropped} with no correct candidate\nsaved {args.out}")


def _rest(method, path, body=None):
    import urllib.request
    req = urllib.request.Request(f"https://api.fireworks.ai/v1/{path}", method=method, data=json.dumps(body).encode() if body else None,
                                 headers={"Authorization": f"Bearer {os.environ['FIREWORKS_API_KEY']}", "Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=300) as r:
        return json.load(r) if r.length != 0 else {}


def promote(args):
    """Register the session's sampler checkpoint as accounts/raheeldeal/models/<model-id> (no deployment, no cost) so it
    survives session deletion and can be deployed later (DEPLOY.md). Docs: after the session is deleted, promotion returns NOT_FOUND."""
    info = json.load(open(args.session))
    ck = _rest("GET", f"{info['session_name']}/checkpoints?pageSize=200").get("trainingSessionCheckpoints", [])
    print(json.dumps(ck, indent=1)[:1500])
    cands = [c for c in ck if c.get("promotable")] or ck
    if not cands:
        sys.exit("no checkpoints listed for this session")
    target = sorted(cands, key=lambda c: c.get("createTime", ""))[-1]
    res = _rest("POST", f"{target['name']}:promote", {"output_model": f"accounts/raheeldeal/models/{args.model_id}", "base_model": BASE_MODEL})
    info["promoted_model"] = res.get("name", f"accounts/raheeldeal/models/{args.model_id}")
    info["promoted_from"] = target["name"]
    json.dump(info, open(args.session, "w"), indent=1)
    print("promoted", target["name"], "->", info["promoted_model"])


def cleanup(args):
    import urllib.request
    name = args.session
    if name.endswith(".json"):
        name = json.load(open(name))["session_name"]
    req = urllib.request.Request(f"https://api.fireworks.ai/v1/{name}", method="DELETE",
                                 headers={"Authorization": f"Bearer {os.environ['FIREWORKS_API_KEY']}"})
    with urllib.request.urlopen(req, timeout=60) as r:
        print("deleted", name, r.status)


def main():
    ap = argparse.ArgumentParser()
    sp = ap.add_subparsers(dest="cmd", required=True)
    p = sp.add_parser("plan"); p.add_argument("--data", required=True); p.add_argument("--epochs", type=int, default=2)
    p = sp.add_parser("train"); p.add_argument("--data", required=True); p.add_argument("--tag", required=True)
    p.add_argument("--epochs", type=int, default=2); p.add_argument("--batch", type=int, default=16); p.add_argument("--rank", type=int, default=8)
    p.add_argument("--lr", type=float, default=1e-4); p.add_argument("--slot-retries", type=int, default=30)
    p = sp.add_parser("eval"); p.add_argument("--model", required=True); p.add_argument("--out", required=True)
    p.add_argument("--max-tokens", type=int, default=32); p.add_argument("--limit", type=int, default=0); p.add_argument("--workers", type=int, default=4)
    p = sp.add_parser("sample"); p.add_argument("--model", required=True); p.add_argument("--data", required=True); p.add_argument("--out", required=True)
    p.add_argument("--n", type=int, default=4); p.add_argument("--temp", type=float, default=0.8); p.add_argument("--max-tokens", type=int, default=32)
    p.add_argument("--limit", type=int, default=0); p.add_argument("--workers", type=int, default=4)
    p = sp.add_parser("select"); p.add_argument("--candidates", required=True); p.add_argument("--out", required=True)
    p = sp.add_parser("promote"); p.add_argument("--session", required=True); p.add_argument("--model-id", required=True)
    p = sp.add_parser("cleanup"); p.add_argument("--session", required=True)
    args = ap.parse_args()
    {"plan": plan, "train": train, "eval": evaluate, "sample": sample, "select": select, "promote": promote, "cleanup": cleanup}[args.cmd](args)


if __name__ == "__main__":
    main()
