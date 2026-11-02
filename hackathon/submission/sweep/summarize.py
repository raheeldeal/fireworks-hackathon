#!/usr/bin/env python3
"""SWEEP table from sweep/results/*.json. Per config: accuracy, invalid, p50/p95, $/1k, mean prompt/answer/reasoning tokens per call,
catalog share of prompt tokens (measured catalog tokens from catalog_tokens.json / mean prompt tokens) and catalog share of cost.
Usage: python3 summarize.py [--md] [files...]"""
import json, glob, os, sys
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, os.path.dirname(HERE))
import fw
CAT = json.load(open(os.path.join(HERE, "catalog_tokens.json")))
def metrics(d):
    rows = d["rows"]; n = len(rows); m = d["model"].split("/")[-1]
    tin = d["in_tokens"] / n; tout = d["out_tokens"] / n; trs = d["reasoning_tokens"] / n
    cat = CAT.get(m, {}).get("catalog_tokens")
    pi, po = fw.PRICING[d["model"]]
    cost_call = (tin * pi + tout * po) / 1e6
    return {"model": m, "tag": d["tag"], "n": n, "accuracy": d["accuracy"], "invalid": d["invalid_outputs"],
            "p50": d["p50_latency_s"], "p95": d["p95_latency_s"], "cost_1k": d["cost_per_1k_requests_usd"],
            "prompt_tok": tin, "answer_tok": tout - trs, "reasoning_tok": trs, "catalog_tok": cat,
            "catalog_share_prompt": (cat / tin) if cat else None,
            "catalog_share_cost": (cat * pi / 1e6 / cost_call) if cat and cost_call else None,
            "length_stops": sum(r["finish_reason"] == "length" for r in rows),
            "reused": d.get("reused_from"), "file": None}
if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    paths = args or sorted(p for p in glob.glob(os.path.join(HERE, "results", "*.json")) if "route" not in os.path.basename(p))
    ms = []
    for p in paths:
        d = json.load(open(p)); x = metrics(d); x["file"] = os.path.relpath(p, HERE); ms.append(x)
    ms.sort(key=lambda x: (-x["accuracy"], x["cost_1k"]))
    print("| model | config | n | accuracy | invalid | len-cap | p50 s | p95 s | $/1k | prompt tok | answer tok | reasoning tok | catalog tok | catalog % of prompt | catalog % of cost | file |")
    print("|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|")
    for x in ms:
        print(f"| {x['model']} | {x['tag']} | {x['n']} | {x['accuracy']:.1%} | {x['invalid']} | {x['length_stops']} | {x['p50']:.2f} | {x['p95']:.2f} | {x['cost_1k']:.3f} | {x['prompt_tok']:.0f} | {x['answer_tok']:.0f} | {x['reasoning_tok']:.0f} | {x['catalog_tok'] or '-'} | {x['catalog_share_prompt']:.0%} | {x['catalog_share_cost']:.0%} | {x['file']}{' (reused)' if x['reused'] else ''} |")
