#!/usr/bin/env python3
"""Latency + token benchmark of a deployed model on the locked test set. Stdlib only.

  python3 bench.py --model "accounts/raheeldeal/models/tool-router#accounts/raheeldeal/deployments/<id>" --bare --n 50
  python3 bench.py --model accounts/fireworks/models/glm-5p3-flash --catalog --n 50

--bare    : system "Reply with the single best tool name." + user request (tuned model)
--catalog : prompts/v1_plain.txt with the 100-tool catalog substituted (stock model)
Prints accuracy, p50/p95 latency, mean prompt/completion tokens; writes results/bench_<label>.json.
"""
import argparse, json, os, statistics, sys, time, urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
SUB = os.path.dirname(HERE)
sys.path.insert(0, SUB)
import score  # noqa: E402

URL = "https://api.fireworks.ai/inference/v1/chat/completions"
BARE = "Reply with the single best tool name."


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", required=True)
    ap.add_argument("--bare", action="store_true")
    ap.add_argument("--catalog", action="store_true")
    ap.add_argument("--n", type=int, default=50)
    ap.add_argument("--max-tokens", type=int, default=32)
    ap.add_argument("--label", default=None)
    a = ap.parse_args()
    if a.catalog:
        system = open(os.path.join(SUB, "prompts", "v1_plain.txt")).read().replace("{CATALOG}", open(os.path.join(SUB, "data", "catalog.txt")).read().strip())
    else:
        system = BARE
    rows = [json.loads(l) for l in open(os.path.join(SUB, "data", "test.jsonl")) if l.strip()][: a.n]
    key = os.environ["FIREWORKS_API_KEY"]
    out = []
    for r in rows:
        body = {"model": a.model, "max_tokens": a.max_tokens, "temperature": 0,
                "messages": [{"role": "system", "content": system}, {"role": "user", "content": r["text"]}]}
        if "glm" in a.model:
            body["reasoning_effort"] = "low"
        req = urllib.request.Request(URL, data=json.dumps(body).encode(), headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"})
        t0 = time.time()
        with urllib.request.urlopen(req, timeout=120) as resp:
            d = json.load(resp)
        lat = time.time() - t0
        text = d["choices"][0]["message"].get("content") or ""
        u = d.get("usage", {})
        s = score.score(text, r["label"])
        out.append({"id": r["id"], "pred": s["pred"], "correct": s["top1"], "latency": round(lat, 3),
                    "in_tokens": u.get("prompt_tokens", 0), "out_tokens": u.get("completion_tokens", 0)})
        print(("✓" if s["top1"] else "✗"), f"{r['label']:28s} {s['pred']:28s} {lat:.2f}s in={out[-1]['in_tokens']} out={out[-1]['out_tokens']}", flush=True)
    lat = sorted(x["latency"] for x in out)
    n = len(out)
    summ = {"model": a.model, "prompt": "catalog" if a.catalog else "bare", "n": n, "accuracy": round(sum(x["correct"] for x in out) / n, 4),
            "p50_latency_s": round(statistics.median(lat), 3), "p95_latency_s": round(lat[int(0.95 * (n - 1))], 3),
            "in_tokens_per_call": round(sum(x["in_tokens"] for x in out) / n, 1), "out_tokens_per_call": round(sum(x["out_tokens"] for x in out) / n, 2), "rows": out}
    label = a.label or ("stock_catalog" if a.catalog else "tuned_bare")
    p = os.path.join(HERE, "results", f"bench_{label}.json")
    json.dump(summ, open(p, "w"), indent=1)
    print(json.dumps({k: v for k, v in summ.items() if k != "rows"}, indent=1), "\nsaved", p)


if __name__ == "__main__":
    main()
