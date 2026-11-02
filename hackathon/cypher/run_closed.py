#!/usr/bin/env python3
"""Closed-model reference bar for the text-to-Cypher exam (Anthropic or OpenAI).

Same locked test set, same prompt, same execution scoring as run_eval.py, so the result file
drops straight into the chart.

    export ANTHROPIC_API_KEY=sk-ant-...        # then:
    .venv/bin/python run_closed.py --provider anthropic --model claude-opus-5 --limit 100

    export OPENAI_API_KEY=sk-...               # or:
    .venv/bin/python run_closed.py --provider openai --model gpt-5 --limit 100

Writes results/<model>_v1_plain_n<limit>.json and appends to ledger_closed.csv.
Prices are per 1M tokens; override with --price-in / --price-out if they are wrong.
"""
import argparse, csv, json, os, statistics, sys, threading, time, urllib.request, urllib.error
from concurrent.futures import ThreadPoolExecutor
from executor import execute
from score import score, clean_pred

HERE = os.path.dirname(os.path.abspath(__file__))
LEDGER = os.path.join(HERE, "ledger_closed.csv")
DEFAULT_PRICES = {  # $ per 1M tokens (input, output) — verify before quoting
    "anthropic": (5.00, 25.00),
    "openai": (1.25, 10.00),
}
_lock = threading.Lock()


def call_anthropic(model, system, user, max_tokens):
    key = os.environ.get("ANTHROPIC_API_KEY")
    if not key:
        sys.exit("ANTHROPIC_API_KEY not set")
    body = json.dumps({
        "model": model,
        "max_tokens": max_tokens,
        "temperature": 0,
        "system": system,
        "messages": [{"role": "user", "content": user}],
    }).encode()
    req = urllib.request.Request(
        "https://api.anthropic.com/v1/messages",
        data=body,
        headers={"x-api-key": key, "anthropic-version": "2023-06-01", "content-type": "application/json"},
    )
    t0 = time.time()
    with urllib.request.urlopen(req, timeout=180) as r:
        d = json.load(r)
    text = "".join(b.get("text", "") for b in d.get("content", []) if b.get("type") == "text")
    u = d.get("usage", {})
    return text, time.time() - t0, u.get("input_tokens", 0), u.get("output_tokens", 0)


def call_openai(model, system, user, max_tokens):
    key = os.environ.get("OPENAI_API_KEY")
    if not key:
        sys.exit("OPENAI_API_KEY not set")
    body = json.dumps({
        "model": model,
        "max_completion_tokens": max_tokens,
        "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
    }).encode()
    req = urllib.request.Request(
        "https://api.openai.com/v1/chat/completions",
        data=body,
        headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
    )
    t0 = time.time()
    with urllib.request.urlopen(req, timeout=180) as r:
        d = json.load(r)
    text = d["choices"][0]["message"].get("content") or ""
    u = d.get("usage", {})
    return text, time.time() - t0, u.get("prompt_tokens", 0), u.get("completion_tokens", 0)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--provider", required=True, choices=["anthropic", "openai"])
    ap.add_argument("--model", required=True)
    ap.add_argument("--prompt", default=os.path.join(HERE, "prompts", "v1_plain.txt"))
    ap.add_argument("--data", default=os.path.join(HERE, "data", "test.jsonl"))
    ap.add_argument("--limit", type=int, default=100)
    ap.add_argument("--max-tokens", type=int, default=1024)
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--price-in", type=float)
    ap.add_argument("--price-out", type=float)
    ap.add_argument("--cap", type=float, default=5.0, help="stop if estimated spend exceeds this")
    a = ap.parse_args()

    pin, pout = DEFAULT_PRICES[a.provider]
    if a.price_in is not None:
        pin = a.price_in
    if a.price_out is not None:
        pout = a.price_out
    call = call_anthropic if a.provider == "anthropic" else call_openai
    tmpl = open(a.prompt).read()
    rows_in = [json.loads(l) for l in open(a.data) if l.strip()][: a.limit]
    out_rows, spent = [], {"usd": 0.0}

    def one(ex):
        system = tmpl.replace("{schema}", ex["schema"]) if "{schema}" in tmpl else tmpl + "\n\nSchema:\n" + ex["schema"]
        try:
            raw, lat, ti, to = call(a.model, system, ex["question"], a.max_tokens)
        except urllib.error.HTTPError as e:
            return {"id": ex.get("instance_id") or ex.get("id"), "tier": ex.get("tier"), "graph": ex.get("database_reference_alias"),
                    "pred_cypher": "", "exec_status": "error", "correct": False, "latency": 0.0,
                    "in_tokens": 0, "out_tokens": 0, "raw": f"HTTP {e.code}: {e.read()[:200]!r}"}
        pred = clean_pred(raw)
        res = execute(ex["database_reference_alias"], pred)
        st, ok = score(res, ex.get("gold_result"))
        cost = (ti * pin + to * pout) / 1_000_000
        with _lock:
            spent["usd"] += cost
        return {"id": ex.get("instance_id") or ex.get("id"), "tier": ex.get("tier"), "graph": ex.get("database_reference_alias"),
                "pred_cypher": pred, "exec_status": st, "correct": bool(ok), "latency": lat,
                "in_tokens": ti, "out_tokens": to, "cost": cost, "raw": raw[:400]}

    with ThreadPoolExecutor(max_workers=a.workers) as pool:
        for i, r in enumerate(pool.map(one, rows_in), 1):
            out_rows.append(r)
            print(("+" if r["correct"] else "-"), end="", flush=True)
            if spent["usd"] > a.cap:
                print("\ncap reached, stopping")
                break
    print()

    n = len(out_rows)
    lats = sorted(r["latency"] for r in out_rows) or [0]
    acc = sum(r["correct"] for r in out_rows) / n
    summary = {
        "model": a.model, "provider": a.provider, "prompt": os.path.basename(a.prompt).split(".")[0],
        "n": n, "accuracy": round(acc, 4),
        "error_rate": round(sum(r["exec_status"] == "error" for r in out_rows) / n, 4),
        "empty_rate": round(sum(r["exec_status"] == "empty" for r in out_rows) / n, 4),
        "p50_latency_s": round(statistics.median(lats), 3),
        "p95_latency_s": round(lats[int(0.95 * (n - 1))], 3),
        "cost_per_1k_requests_usd": round(spent["usd"] / n * 1000, 4),
        "rows": out_rows,
    }
    os.makedirs(os.path.join(HERE, "results"), exist_ok=True)
    path = os.path.join(HERE, "results", f"{a.model.replace('/', '-')}_v1_plain_n{n}.json")
    json.dump(summary, open(path, "w"), indent=2)
    new = not os.path.exists(LEDGER)
    with open(LEDGER, "a", newline="") as f:
        w = csv.writer(f)
        if new:
            w.writerow(["ts", "model", "n", "cost"])
        w.writerow([time.strftime("%Y-%m-%dT%H:%M:%S"), a.model, n, round(spent['usd'], 4)])
    print(f"{a.model}: {acc:.1%} on {n} | p50 {summary['p50_latency_s']}s | ${summary['cost_per_1k_requests_usd']}/1k | spent ${spent['usd']:.2f}")
    print("saved", path)


if __name__ == "__main__":
    main()
