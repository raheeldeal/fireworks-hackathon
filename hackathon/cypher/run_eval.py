#!/usr/bin/env python3
"""Text-to-Cypher eval: one model + one prompt over data/test.jsonl, scored by execution.

Adapted from hackathon/eval/run_eval.py; keeps its results JSON shape and adds per-row
pred_cypher, exec_status, latency, in/out/reasoning tokens.

  .venv/bin/python run_eval.py --model accounts/fireworks/models/glm-5p3-flash --prompt prompts/v1_plain.txt
  .venv/bin/python run_eval.py --model gold   # sanity: re-executes gold queries, no API cost
"""
import argparse, csv, datetime, json, logging, os, statistics, sys, threading, time, urllib.request, urllib.error
from concurrent.futures import ThreadPoolExecutor
from executor import execute
from score import score, score_lenient, clean_pred

logging.getLogger("neo4j").setLevel(logging.ERROR)
HERE = os.path.dirname(os.path.abspath(__file__))
LEDGER = os.path.join(HERE, "ledger.csv")
CAP_USD = 4.00
PRICING = {  # $ per 1M tokens (input, output), PROTOCOL.md 2026-11-01
    "accounts/fireworks/models/nemotron-lightning-3p5-30b-a3b": (0.05, 0.20),
    "accounts/fireworks/models/glm-5p3-flash": (0.15, 0.50),
    "accounts/fireworks/models/gpt-oss-120b": (0.15, 0.60),
    "accounts/fireworks/models/deepseek-v4p1-flash": (0.30, 1.20),
    "accounts/fireworks/models/glm-5p3": (1.40, 4.40),
    "accounts/fireworks/models/kimi-k3": (3.00, 15.00),
    "gold": (0.0, 0.0),
}
_lock = threading.Lock()
_spent = {"run": 0.0}


def ledger_total():
    if not os.path.exists(LEDGER):
        return 0.0
    with open(LEDGER) as f:
        return sum(float(r["cost"]) for r in csv.DictReader(f))


def ledger_add(model, tin, tout, cost, note):
    new = not os.path.exists(LEDGER)
    with open(LEDGER, "a", newline="") as f:
        w = csv.writer(f)
        if new:
            w.writerow(["timestamp", "model", "in_tokens", "out_tokens", "cost", "note"])
        w.writerow([datetime.datetime.now().isoformat(timespec="seconds"), model, tin, tout, f"{cost:.6f}", note])


def fireworks_call(model, system_prompt, question, max_tokens, extra):
    body = {"model": model, "max_tokens": max_tokens, "temperature": 0,
            "messages": [{"role": "system", "content": system_prompt}, {"role": "user", "content": question}]}
    body.update(extra)
    data = json.dumps(body).encode()
    for attempt in range(6):
        req = urllib.request.Request("https://api.fireworks.ai/inference/v1/chat/completions", data=data,
                                     headers={"Authorization": f"Bearer {os.environ['FIREWORKS_API_KEY']}",
                                              "Content-Type": "application/json"})
        t0 = time.time()
        try:
            with urllib.request.urlopen(req, timeout=180) as resp:
                out = json.load(resp)
            lat = time.time() - t0
            msg = out["choices"][0]["message"]
            u = out.get("usage", {})
            reasoning = (u.get("completion_tokens_details") or {}).get("reasoning_tokens") or 0
            return {"raw": msg.get("content") or "", "latency": lat, "in": u.get("prompt_tokens", 0),
                    "out": u.get("completion_tokens", 0), "reasoning": reasoning,
                    "finish": out["choices"][0].get("finish_reason"), "api_error": None}
        except urllib.error.HTTPError as e:
            err = f"HTTP {e.code}: {e.read()[:200]!r}"
            if e.code in (429, 500, 502, 503, 504) and attempt < 5:
                time.sleep(2 ** attempt); continue
            return {"raw": "", "latency": time.time() - t0, "in": 0, "out": 0, "reasoning": 0, "finish": None, "api_error": err}
        except Exception as e:
            if attempt < 5:
                time.sleep(2 ** attempt); continue
            return {"raw": "", "latency": time.time() - t0, "in": 0, "out": 0, "reasoning": 0, "finish": None, "api_error": repr(e)[:200]}


def pct(xs, p):
    s = sorted(xs)
    return s[int(p * (len(s) - 1))] if s else 0.0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", required=True)
    ap.add_argument("--prompt", default=os.path.join(HERE, "prompts", "v1_plain.txt"))
    ap.add_argument("--data", default=os.path.join(HERE, "data", "test.jsonl"))
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--max-tokens", type=int, default=4096)
    ap.add_argument("--extra", default="{}", help="JSON merged into the request body, e.g. '{\"reasoning_effort\":\"none\"}'")
    ap.add_argument("--workers", type=int, default=6)
    ap.add_argument("--tag", default="")
    ap.add_argument("--out")
    args = ap.parse_args()

    examples = [json.loads(l) for l in open(args.data) if l.strip()]
    if args.limit:
        examples = examples[: args.limit]
    template = open(args.prompt).read()
    prompt_name = os.path.splitext(os.path.basename(args.prompt))[0] + (f"_{args.tag}" if args.tag else "")
    extra = json.loads(args.extra)
    pin, pout = PRICING[args.model]
    start_total = ledger_total()
    if args.model != "gold" and start_total >= CAP_USD:
        sys.exit(f"ledger at ${start_total:.2f} >= cap ${CAP_USD}")

    def one(ex):
        if args.model == "gold":
            r = {"raw": ex["cypher"], "latency": 0.0, "in": 0, "out": 0, "reasoning": 0, "finish": "gold", "api_error": None}
        else:
            with _lock:
                if start_total + _spent["run"] >= CAP_USD:
                    return None
            r = fireworks_call(args.model, template.replace("{schema}", ex["schema"]), ex["question"], args.max_tokens, extra)
            with _lock:
                _spent["run"] += (r["in"] * pin + r["out"] * pout) / 1e6
        pred = clean_pred(r["raw"])
        res = execute(ex["graph"], pred) if pred else {"ok": False, "rows": [], "columns": [], "error": "no query", "secs": 0}
        gold = {"ok": True, **ex["gold_result"]}
        status = score(gold, res, ex["cypher"])
        lenient = score_lenient(gold, res, ex["cypher"])
        return {"id": ex["id"], "graph": ex["graph"], "tier": ex["complexity"]["tier"], "complexity": ex["complexity"],
                "question": ex["question"], "gold_cypher": ex["cypher"], "raw": r["raw"], "pred_cypher": pred,
                "exec_status": status, "lenient_status": lenient, "exec_error": res.get("error"), "pred_n_rows": len(res["rows"]), "pred_rows_head": res["rows"][:5],
                "correct": status == "correct", "pred": status, "label": "correct",
                "latency": round(r["latency"], 3), "in_tokens": r["in"], "out_tokens": r["out"],
                "reasoning_tokens": r["reasoning"], "finish_reason": r["finish"], "api_error": r["api_error"]}

    with ThreadPoolExecutor(args.workers) as pool:
        rows = [x for x in pool.map(one, examples) if x is not None]
    n = len(rows)
    tin = sum(r["in_tokens"] for r in rows); tout = sum(r["out_tokens"] for r in rows)
    cost = (tin * pin + tout * pout) / 1e6
    if args.model != "gold":
        ledger_add(args.model, tin, tout, cost, f"{prompt_name} n={n}")
    lats = [r["latency"] for r in rows]
    cnt = lambda s: sum(r["exec_status"] == s for r in rows)

    def breakdown(key):
        out = {}
        for k in sorted({r[key] for r in rows}):
            rs = [r for r in rows if r[key] == k]
            out[k] = {"n": len(rs), "accuracy": round(sum(r["correct"] for r in rs) / len(rs), 4),
                      "accuracy_lenient": round(sum(r["lenient_status"] == "correct" for r in rs) / len(rs), 4),
                      "error": sum(r["exec_status"] == "error" for r in rs), "empty": sum(r["exec_status"] == "empty" for r in rs)}
        return out

    summary = {
        "model": args.model, "prompt": prompt_name, "mock": False, "n": n,
        "accuracy": round(cnt("correct") / n, 4),
        "accuracy_lenient": round(sum(r["lenient_status"] == "correct" for r in rows) / n, 4),
        "invalid_outputs": cnt("error"),
        "error_rate": round(cnt("error") / n, 4), "empty_rate": round(cnt("empty") / n, 4), "wrong_rate": round(cnt("wrong") / n, 4),
        "p50_latency_s": round(statistics.median(lats), 3), "p95_latency_s": round(pct(lats, 0.95), 3),
        "cost_per_1k_requests_usd": round(cost / n * 1000, 4), "cost_total_usd": round(cost, 4),
        "in_tokens": tin, "out_tokens": tout, "reasoning_tokens": sum(r["reasoning_tokens"] for r in rows),
        "api_errors": sum(1 for r in rows if r["api_error"]), "truncated": sum(1 for r in rows if r["finish_reason"] == "length"),
        "request_extra": extra, "max_tokens": args.max_tokens,
        "test_sha256": open(os.path.join(HERE, "data", "TEST_HASH")).read().split()[0],
        "by_graph": breakdown("graph"), "by_tier": breakdown("tier"),
        "rows": rows,
    }
    out = args.out or os.path.join(HERE, "results", f"{args.model.split('/')[-1]}_{prompt_name}_n{n}.json")
    os.makedirs(os.path.dirname(out), exist_ok=True)
    json.dump(summary, open(out, "w"), indent=1, default=str)
    print(f"{args.model} {prompt_name}: acc {summary['accuracy']:.1%} lenient {summary['accuracy_lenient']:.1%} err {summary['error_rate']:.1%} empty {summary['empty_rate']:.1%} "
          f"p50 {summary['p50_latency_s']}s p95 {summary['p95_latency_s']}s ${summary['cost_per_1k_requests_usd']}/1k "
          f"cost ${cost:.4f} trunc {summary['truncated']} apierr {summary['api_errors']} | ledger ${ledger_total():.4f}")
    print("saved", out)


if __name__ == "__main__":
    main()
