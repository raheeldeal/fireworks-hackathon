#!/usr/bin/env python3
"""Text-to-Cypher fine-tuning of Muse Glimmer 30B via the Fireworks Serverless Training API: SFT, then execution-reward RFT.

No dataset upload, no deployment. Training on Muse Glimmer 30B is free until 2026-11-30 (docs.fireworks.ai/fine-tuning/models.md);
sampling is billed per token (prefill $1.96/M, sample $4.88/M; repeated prefixes bill 80% off, we log full price) -> ledger.csv.

  PY="env PYTHONPATH=train/.pylib ../runs/regex/venv311/bin/python"     # run from hackathon/cypher
  $PY train/rl.py eval   --model base --out results/train_base.json
  $PY train/rl.py train  --data data/train.jsonl --tag sft              # -> train/results/sft_session.json (session deleted at end)
  $PY train/rl.py eval   --model <sampler path> --out results/train_sft.json [--prune]
  $PY train/rl.py sample --model <sampler path> --out train/results/r1_cands.jsonl     # 4 cands/question @0.8, executed + rewarded
  $PY train/rl.py build  --cands train/results/r1_cands.jsonl --mode weighted --out train/data/r1.jsonl
  $PY train/rl.py train  --data train/data/r1.jsonl --tag r1 --from-state <sft state path> --lr 2e-5
Prompt (train = test): system = prompts/v1_plain.txt with {schema} filled, user = question. Same as run_eval.py.
"""
import argparse, csv, json, os, random, statistics, sys, threading, time, urllib.request
from concurrent.futures import ThreadPoolExecutor
import logging

HERE = os.path.dirname(os.path.abspath(__file__))
CY = os.path.dirname(HERE)
sys.path.insert(0, CY)
sys.path.insert(0, os.path.join(CY, "harness"))
from executor import execute, normalize_cypher  # noqa: E402
from score import score, score_lenient, clean_pred  # noqa: E402

logging.getLogger("neo4j").setLevel(logging.ERROR)
BASE_MODEL = "accounts/fireworks/models/muse-glimmer-30b"
TOKENIZER = "meta-models/Muse-Glimmer-30B"
SERVERLESS_URL = "https://api.fireworks.ai/training/v1/serverless"
PRICE_PREFILL, PRICE_SAMPLE = 1.96, 4.88
CAP = 6.00
LEDGER = os.path.join(HERE, "ledger.csv")
SYSTEM_T = open(os.path.join(CY, "prompts", "v1_plain.txt")).read()
SEED = 0
_lk = threading.Lock()


def load_jsonl(p):
    return [json.loads(l) for l in open(p) if l.strip()]


def ledger_total():
    if not os.path.exists(LEDGER):
        return 0.0
    return sum(float(r["cost"]) for r in csv.DictReader(open(LEDGER)))


def ledger_add(model, tin, tout, note):
    cost = (tin * PRICE_PREFILL + tout * PRICE_SAMPLE) / 1e6
    with _lk:
        new = not os.path.exists(LEDGER)
        with open(LEDGER, "a", newline="") as f:
            w = csv.writer(f)
            if new:
                w.writerow(["timestamp", "model", "in_tokens", "out_tokens", "cost", "note"])
            w.writerow([time.strftime("%Y-%m-%dT%H:%M:%S"), model, tin, tout, f"{cost:.6f}", note])
    return cost


def get_tokenizer():
    from transformers import AutoTokenizer
    return AutoTokenizer.from_pretrained(TOKENIZER)


def _ids(tok, text):
    return list(tok(text, add_special_tokens=False)["input_ids"])


def system_for(row, prune=False):
    schema = row["schema"]
    if prune:
        from harness import schema_prune
        schema = schema_prune(row["question"], schema)[0]  # returns (text, pruned?)
    return SYSTEM_T.replace("{schema}", schema)


def render(tok, system, user, assistant=None):
    msgs = [{"role": "system", "content": system}, {"role": "user", "content": user}]
    prompt = _ids(tok, tok.apply_chat_template(msgs, tokenize=False, add_generation_prompt=True, reasoning_strength="low"))
    if assistant is None:
        return prompt, None
    full = _ids(tok, tok.apply_chat_template(msgs + [{"role": "assistant", "content": assistant}], tokenize=False, reasoning_strength="low"))
    assert full[: len(prompt)] == prompt, "chat template prefix mismatch"
    return prompt, full


def answer_prefill(tok):
    """Muse answers as '<|start|>assistant to=user<|message|>ANSWER<|eot|>'. Prefilling ' to=user<|message|>' skips the
    to=self reasoning channel (reasoning off). Base, SFT and RFT are all sampled with it, and SFT targets include it."""
    msg_id = tok.convert_tokens_to_ids("<|message|>")
    p, full = render(tok, "s", "probe", "x")
    return full[len(p): len(full) - full[::-1].index(msg_id)]


def parse_reply(text):
    if "<|message|>" in text:
        text = text.split("<|message|>")[-1]
    for t in ("<|eot|>", "<|end_of_text|>", "<|start|>", "<|end|>"):
        text = text.split(t)[0]
    return text.strip()


def service_client():
    from fireworks.training.sdk import FiretitanServiceClient
    return FiretitanServiceClient(api_key=os.environ["FIREWORKS_API_KEY"], base_url=SERVERLESS_URL)


# ---------- reward (RFT) ----------
GOLD_CACHE = os.path.join(HERE, "data", "train_gold.json")


def gold_for(rows):
    """Train rows carry only the gold Cypher; execute it once (read-only) and cache the result rows."""
    cache = json.load(open(GOLD_CACHE)) if os.path.exists(GOLD_CACHE) else {}
    todo = [r for r in rows if r["id"] not in cache and "gold_result" not in r]
    if todo:
        with ThreadPoolExecutor(8) as pool:
            for r, res in zip(todo, pool.map(lambda r: execute(r["graph"], r["cypher"]), todo)):
                cache[r["id"]] = {"rows": res["rows"], "columns": res["columns"], "ok": res["ok"], "error": res["error"]}
        os.makedirs(os.path.dirname(GOLD_CACHE), exist_ok=True)
        json.dump(cache, open(GOLD_CACHE, "w"), default=str)
    for r in rows:
        if "gold_result" not in r:
            g = cache[r["id"]]
            r["gold_result"] = {"rows": g["rows"], "columns": g["columns"]}
            r["gold_ok"] = g["ok"]
    return rows


def reward(row, cypher):
    """1.0 if the candidate query executes and its result set equals gold under score.py (unordered multiset of rows,
    column names ignored, floats to 3 dp); 0.0 for wrong rows, execution errors, empty results and unparseable output."""
    pred = clean_pred(cypher)
    if not pred:
        return 0.0, "error", None
    res = execute(row["graph"], pred)
    status = score({"ok": True, **row["gold_result"]}, res, row["cypher"])
    return (1.0 if status == "correct" else 0.0), status, res


# ---------- sampling ----------
def sample_rows(tok, sampler, rows, n, temp, max_tokens, note, workers, prune=False):
    from fireworks.training import sdk
    prefill = answer_prefill(tok)
    eot = tok.convert_tokens_to_ids("<|eot|>")
    params = sdk.SamplingParams(max_tokens=max_tokens, temperature=temp, stop=[eot], seed=SEED if temp > 0 else None)
    done = [0]

    def one(r):
        if ledger_total() >= CAP:
            raise RuntimeError(f"ledger ${ledger_total():.2f} >= cap ${CAP}")
        prompt = render(tok, system_for(r, prune), r["question"])[0] + prefill
        t0, res, err = time.time(), None, None
        for attempt in range(6):
            try:
                res = sampler.sample(prompt=sdk.ModelInput.from_ints(prompt), num_samples=n, sampling_params=params).result()
                break
            except Exception as e:
                err = str(e)[:200]
                time.sleep(2 ** attempt)
        lat = time.time() - t0
        cands = []
        for seq in ((res.sequences or []) if res else []):
            toks = list(seq.tokens or [])
            raw = tok.decode(toks, skip_special_tokens=False)
            n_out = len([t for t in toks if t != eot])
            cands.append({"raw": raw, "text": parse_reply(raw), "out_tokens": n_out, "stop": str(getattr(seq, "stop_reason", ""))})
        if res:
            ledger_add(BASE_MODEL + " (sampler)", len(prompt), sum(c["out_tokens"] + 1 for c in cands), note)
        with _lk:
            done[0] += 1
            if done[0] % 25 == 0:
                print(f"  sampled {done[0]}/{len(rows)} ledger ${ledger_total():.3f}", flush=True)
        return {"row": r, "in_tokens": len(prompt), "latency": round(lat, 3), "cands": cands, "api_error": None if res else err}

    with ThreadPoolExecutor(max_workers=workers) as pool:
        return list(pool.map(one, rows))


def make_sampler(service, tok, model):
    if model == "base":
        return service.create_sampling_client(base_model=BASE_MODEL, tokenizer=tok)
    return service.create_sampling_client(model_path=model, tokenizer=tok)


def evaluate(args):
    tok = get_tokenizer()
    rows = load_jsonl(os.path.join(CY, "data", "test.jsonl"))
    if args.limit:
        rows = rows[: args.limit]
    service = service_client()
    sampler = make_sampler(service, tok, args.model)
    label = os.path.splitext(os.path.basename(args.out))[0]
    recs = sample_rows(tok, sampler, rows, 1, 0.0, args.max_tokens, f"eval {label}", args.workers, prune=args.prune)

    def score_one(rec):
        ex = rec["row"]
        c = rec["cands"][0] if rec["cands"] else {"raw": "", "text": "", "out_tokens": 0, "stop": "error"}
        pred = clean_pred(c["text"])
        res = execute(ex["graph"], pred) if pred else {"ok": False, "rows": [], "columns": [], "error": "no query", "secs": 0}
        gold = {"ok": True, **ex["gold_result"]}
        status = score(gold, res, ex["cypher"])
        lenient = score_lenient(gold, res, ex["cypher"])
        return {"id": ex["id"], "graph": ex["graph"], "tier": ex["complexity"]["tier"], "complexity": ex["complexity"],
                "question": ex["question"], "gold_cypher": ex["cypher"], "raw": c["raw"][:2000], "pred_cypher": pred,
                "exec_status": status, "lenient_status": lenient, "exec_error": res.get("error"), "pred_n_rows": len(res["rows"]),
                "pred_rows_head": res["rows"][:5], "correct": status == "correct", "pred": status, "label": "correct",
                "latency": rec["latency"], "in_tokens": rec["in_tokens"], "out_tokens": c["out_tokens"], "reasoning_tokens": 0,
                "finish_reason": c["stop"], "api_error": rec["api_error"]}

    with ThreadPoolExecutor(8) as pool:
        out_rows = list(pool.map(score_one, recs))
    n = len(out_rows)
    tin, tout = sum(r["in_tokens"] for r in out_rows), sum(r["out_tokens"] for r in out_rows)
    cost = (tin * PRICE_PREFILL + tout * PRICE_SAMPLE) / 1e6
    lats = sorted(r["latency"] for r in out_rows)
    cnt = lambda s: sum(r["exec_status"] == s for r in out_rows)

    def breakdown(key):
        out = {}
        for k in sorted({r[key] for r in out_rows}):
            rs = [r for r in out_rows if r[key] == k]
            out[k] = {"n": len(rs), "accuracy": round(sum(r["correct"] for r in rs) / len(rs), 4),
                      "accuracy_lenient": round(sum(r["lenient_status"] == "correct" for r in rs) / len(rs), 4),
                      "error": sum(r["exec_status"] == "error" for r in rs), "empty": sum(r["exec_status"] == "empty" for r in rs)}
        return out

    summary = {
        "model": BASE_MODEL if args.model == "base" else f"{BASE_MODEL} + LoRA {args.model}",
        "prompt": "v1_plain" + ("_pruned" if args.prune else ""), "mock": False, "n": n,
        "accuracy": round(cnt("correct") / n, 4),
        "accuracy_lenient": round(sum(r["lenient_status"] == "correct" for r in out_rows) / n, 4),
        "invalid_outputs": cnt("error"),
        "error_rate": round(cnt("error") / n, 4), "empty_rate": round(cnt("empty") / n, 4), "wrong_rate": round(cnt("wrong") / n, 4),
        "p50_latency_s": round(statistics.median(lats), 3), "p95_latency_s": round(lats[int(0.95 * (n - 1))], 3),
        "cost_per_1k_requests_usd": round(cost / n * 1000, 4), "cost_total_usd": round(cost, 4),
        "in_tokens": tin, "out_tokens": tout, "in_tokens_per_call": round(tin / n, 1), "out_tokens_per_call": round(tout / n, 1),
        "reasoning_tokens": 0, "api_errors": sum(1 for r in out_rows if r["api_error"]),
        "truncated": sum(1 for r in out_rows if "length" in str(r["finish_reason"]).lower()),
        "request_extra": {"sampler": "serverless training", "temperature": 0, "prefill": "to=user (reasoning off)"},
        "max_tokens": args.max_tokens, "checkpoint": args.model,
        "test_sha256": open(os.path.join(CY, "data", "TEST_HASH")).read().split()[0],
        "pricing_note": "serverless-training sampler rates at full prefill price (prefill $1.96/M, sample $4.88/M); "
                        "production serving of a LoRA needs a dedicated deployment (train/DEPLOY.md)",
        "by_graph": breakdown("graph"), "by_tier": breakdown("tier"), "rows": out_rows}
    os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
    json.dump(summary, open(args.out, "w"), indent=1, default=str)
    print(f"{label}: acc {summary['accuracy']:.1%} lenient {summary['accuracy_lenient']:.1%} err {summary['error_rate']:.1%} "
          f"empty {summary['empty_rate']:.1%} | tiers " + " ".join(f"{k} {v['accuracy']:.0%}" for k, v in summary["by_tier"].items()) +
          f" | in {summary['in_tokens_per_call']} out {summary['out_tokens_per_call']} tok/call | cost ${cost:.3f} | ledger ${ledger_total():.3f}"
          f"\nsaved {args.out}", flush=True)


def sample(args):
    tok = get_tokenizer()
    rows = load_jsonl(args.data)
    if args.limit:
        rows = rows[: args.limit]
    service = service_client()
    sampler = make_sampler(service, tok, args.model)
    rows = gold_for(rows)
    bad = [r["id"] for r in rows if not r.get("gold_ok", True)]
    print(f"gold executed for {len(rows)} train rows; {len(bad)} gold errors (skipped): {bad[:10]}", flush=True)
    rows = [r for r in rows if r.get("gold_ok", True)]
    if args.only:
        keep = set(json.load(open(args.only)))
        rows = [r for r in rows if r["id"] in keep]
        print(f"restricted to {len(rows)} ids from {args.only}", flush=True)
    recs = sample_rows(tok, sampler, rows, args.n, args.temp, args.max_tokens, f"rft sample {os.path.basename(args.out)}", args.workers)
    with open(args.out + ".raw", "w") as f:  # persist paid samples before any scoring
        for r in recs:
            f.write(json.dumps({"id": r["row"]["id"], "cands": r["cands"], "in_tokens": r["in_tokens"], "api_error": r["api_error"]}, default=str) + "\n")

    def rew(rec):
        for c in rec["cands"]:
            c["reward"], c["status"], _ = reward(rec["row"], c["text"])
        return rec

    with ThreadPoolExecutor(8) as pool:
        recs = list(pool.map(rew, recs))
    with open(args.out, "w") as f:
        for r in recs:
            ex = r["row"]
            f.write(json.dumps({"id": ex["id"], "graph": ex["graph"], "question": ex["question"], "cypher": ex["cypher"],
                                "in_tokens": r["in_tokens"], "cands": r["cands"], "api_error": r["api_error"]}, ensure_ascii=False) + "\n")
    allc = [c for r in recs for c in r["cands"]]
    hit = sum(any(c["reward"] > 0 for c in r["cands"]) for r in recs)
    print(f"sampled {len(recs)} x {args.n}: candidate reward mean {statistics.mean(c['reward'] for c in allc):.3f}; "
          f"questions with >=1 correct {hit}/{len(recs)}; ledger ${ledger_total():.3f}\nsaved {args.out}", flush=True)


# ---------- build RFT training file ----------
def build(args):
    """weighted: every distinct candidate of a question with mixed rewards, weight = advantage = reward - mean(reward of the
    question's candidates). Questions where all candidates agree carry no signal (advantage 0) and are skipped.
    reject: one reward-1 candidate per question (shortest), weight 1.0."""
    recs = load_jsonl(args.cands)
    train = {r["id"]: r for r in load_jsonl(os.path.join(CY, "data", "train.jsonl"))}
    out, stats = [], {"questions": len(recs), "mixed": 0, "all1": 0, "all0": 0}
    for r in recs:
        cs = [c for c in r["cands"] if c["text"]]
        if not cs:
            continue
        rs = [c["reward"] for c in cs]
        mean = sum(rs) / len(rs)
        if all(x == 1 for x in rs):
            stats["all1"] += 1
        elif all(x == 0 for x in rs):
            stats["all0"] += 1
        else:
            stats["mixed"] += 1
        base = train[r["id"]]
        if args.mode == "reject":
            good = sorted([c for c in cs if c["reward"] == 1.0], key=lambda c: c["out_tokens"])
            if good:
                out.append({"id": r["id"], "question": base["question"], "schema": base["schema"], "target": good[0]["text"],
                            "weight": 1.0, "reward": 1.0})
        else:
            for c in cs:
                adv = c["reward"] - mean
                if abs(adv) < 1e-9:
                    continue
                out.append({"id": r["id"], "question": base["question"], "schema": base["schema"], "target": c["text"],
                            "weight": round(adv, 4), "reward": c["reward"]})
    os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
    with open(args.out, "w") as f:
        for o in out:
            f.write(json.dumps(o, ensure_ascii=False) + "\n")
    pos = sum(o["weight"] > 0 for o in out)
    print(f"{args.mode}: {len(out)} samples ({pos} positive, {len(out) - pos} negative weight) | {stats}\nsaved {args.out}", flush=True)


# ---------- training ----------
def build_datums(tok, rows, eot_suffix=True):
    from fireworks.training import sdk
    datums, n_tok, n_train = [], 0, 0
    for r in rows:
        target = r.get("target") or normalize_cypher(r["cypher"])
        w = float(r.get("weight", 1.0))
        prompt, full = render(tok, system_for(r), r["question"], target)
        weights = [0.0] * (len(prompt) - 1) + [w] * (len(full) - len(prompt))
        datums.append(sdk.Datum(
            model_input=sdk.ModelInput.from_ints(full[:-1]),
            loss_fn_inputs={"target_tokens": sdk.TensorData(data=full[1:], dtype="int64", shape=[len(full) - 1]),
                            "weights": sdk.TensorData(data=weights, dtype="float32", shape=[len(weights)])}))
        n_tok += len(full)
        n_train += len(full) - len(prompt)
    return datums, n_tok, n_train


def rest(method, path, body=None):
    req = urllib.request.Request(f"https://api.fireworks.ai/v1/{path}", method=method, data=json.dumps(body).encode() if body else None,
                                 headers={"Authorization": f"Bearer {os.environ['FIREWORKS_API_KEY']}", "Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=300) as r:
        txt = r.read()
        return json.loads(txt) if txt else {}


def train(args):
    from fireworks.training import sdk
    tok = get_tokenizer()
    rows = load_jsonl(args.data)
    datums, n_tok, n_train = build_datums(tok, rows)
    print(f"{len(datums)} datums, {n_tok} tokens/epoch, {n_train} loss tokens/epoch, epochs {args.epochs}", flush=True)
    service = service_client()
    for attempt in range(args.slot_retries + 1):
        try:
            if args.from_state:
                try:
                    tc = service.create_training_client_from_state(args.from_state)
                except Exception as e:
                    if "concurrent" in str(e).lower():
                        raise
                    print("from_state failed, warm start via load_state:", str(e)[:200], flush=True)
                    tc = service.create_lora_training_client(base_model=BASE_MODEL, rank=args.rank, seed=SEED)
                    tc.load_state(args.from_state).result()
            else:
                tc = service.create_lora_training_client(base_model=BASE_MODEL, rank=args.rank, seed=SEED)
            break
        except Exception as e:
            if "concurrent" not in str(e).lower() or attempt == args.slot_retries:
                raise
            print(f"slot busy ({str(e)[:100]}), retry in 60s", flush=True)
            time.sleep(60)
    sess_name = getattr(service, "training_session_name", None) or f"accounts/raheeldeal/trainingSessions/{service.training_session_id}"
    info = {"session": service.training_session_id, "session_name": sess_name, "run": tc.run_id,
            "started": time.strftime("%Y-%m-%dT%H:%M:%S"), "tag": args.tag, "data": args.data, "from_state": args.from_state,
            "rows": len(datums), "tokens_per_epoch": n_tok, "loss_tokens_per_epoch": n_train, "epochs": args.epochs,
            "batch": args.batch, "lr": args.lr, "rank": args.rank, "loss_fn": "cross_entropy (per-token weights)", "log": []}
    sess_path = os.path.join(HERE, "results", f"{args.tag}_session.json")
    json.dump(info, open(sess_path, "w"), indent=1)
    print("session", sess_name, "run", tc.run_id, flush=True)
    try:
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
                ls, rt = m.get("loss:sum"), m.get("response_tokens")
                mean = (ls / max(rt, 1.0)) if ls is not None and rt else None
                step += 1
                info["log"].append({"step": step, "epoch": ep, "lr": lr, "mean_loss": mean, "loss_sum": ls, "response_tokens": rt})
                print(f"step {step}/{total} ep {ep} lr {lr:.2e} mean_loss {mean}", flush=True)
            json.dump(info, open(sess_path, "w"), indent=1)
        info["sampler_path"] = tc.save_weights_for_sampler(f"cy-{args.tag}").result().path
        info["state_path"] = tc.save_state(f"cy-{args.tag}-st").result().path
        json.dump(info, open(sess_path, "w"), indent=1)
        print("sampler:", info["sampler_path"], "\nstate:", info["state_path"], flush=True)
        try:  # promote so the LoRA survives session deletion (deployable per DEPLOY.md)
            ck = rest("GET", f"{sess_name}/checkpoints?pageSize=200").get("trainingSessionCheckpoints", [])
            cands = [c for c in ck if c.get("promotable")] or ck
            target = sorted(cands, key=lambda c: c.get("createTime", ""))[-1]
            mid = f"cypher-{args.tag}-{time.strftime('%H%M')}"
            res = rest("POST", f"{target['name']}:promote", {"output_model": f"accounts/raheeldeal/models/{mid}", "base_model": BASE_MODEL})
            info["promoted_model"] = res.get("name", f"accounts/raheeldeal/models/{mid}")
            info["promoted_from"] = target["name"]
            print("promoted ->", info["promoted_model"], flush=True)
        except Exception as e:
            info["promote_error"] = str(e)[:300]
            print("promote failed:", e, flush=True)
        ledger_add(BASE_MODEL + " (serverless training)", 0, 0, f"{args.tag} train {n_tok * args.epochs} tokens, free promo ($0)")
    finally:
        json.dump(info, open(sess_path, "w"), indent=1)
        try:
            service.close()
        except Exception:
            pass
        if not args.keep_session:
            try:
                rest("DELETE", sess_name)
                info["deleted"] = time.strftime("%Y-%m-%dT%H:%M:%S")
                print("deleted session", sess_name, flush=True)
            except Exception as e:
                info["delete_error"] = str(e)[:300]
                print("DELETE FAILED", sess_name, e, flush=True)
            json.dump(info, open(sess_path, "w"), indent=1)


def main():
    ap = argparse.ArgumentParser()
    sp = ap.add_subparsers(dest="cmd", required=True)
    p = sp.add_parser("eval"); p.add_argument("--model", required=True); p.add_argument("--out", required=True)
    p.add_argument("--max-tokens", type=int, default=400); p.add_argument("--limit", type=int, default=0)
    p.add_argument("--workers", type=int, default=8); p.add_argument("--prune", action="store_true")
    p = sp.add_parser("sample"); p.add_argument("--model", required=True); p.add_argument("--out", required=True)
    p.add_argument("--data", default=os.path.join(CY, "data", "train.jsonl"))
    p.add_argument("--n", type=int, default=4); p.add_argument("--temp", type=float, default=0.8); p.add_argument("--only")
    p.add_argument("--max-tokens", type=int, default=400); p.add_argument("--limit", type=int, default=0); p.add_argument("--workers", type=int, default=8)
    p = sp.add_parser("build"); p.add_argument("--cands", required=True); p.add_argument("--out", required=True)
    p.add_argument("--mode", choices=["weighted", "reject"], default="weighted")
    p = sp.add_parser("train"); p.add_argument("--data", required=True); p.add_argument("--tag", required=True)
    p.add_argument("--epochs", type=int, default=2); p.add_argument("--batch", type=int, default=16); p.add_argument("--rank", type=int, default=16)
    p.add_argument("--lr", type=float, default=1e-4); p.add_argument("--slot-retries", type=int, default=20)
    p.add_argument("--from-state"); p.add_argument("--keep-session", action="store_true")
    args = ap.parse_args()
    {"eval": evaluate, "sample": sample, "build": build, "train": train}[args.cmd](args)


if __name__ == "__main__":
    main()
