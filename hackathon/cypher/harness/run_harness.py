#!/usr/bin/env python3
"""Score one harness configuration on the locked test set.

  ../.venv/bin/python run_harness.py --config repair1
  ../.venv/bin/python run_harness.py --config vote3 --seed 2

Writes hackathon/cypher/results/harness_<config>[_s<seed>].json in the run_eval.py shape plus per-row
attempts, exec statuses, tokens, agreement and escalated flag. Ledger: harness/ledger.csv, cap $6.
"""
import argparse, csv, datetime, hashlib, json, logging, os, statistics, sys, threading, time
from concurrent.futures import ThreadPoolExecutor

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import harness as H  # noqa: E402
from score import score, score_lenient  # noqa: E402

logging.getLogger("neo4j").setLevel(logging.ERROR)
CYPHER_DIR = H.CYPHER_DIR
LEDGER = os.path.join(HERE, "ledger.csv")
CAP_USD = 6.00

CONFIGS = {
    "plain":           {"mode": "single", "repair": False, "gate": False},
    "validate_only":   {"mode": "single", "repair": False, "gate": True},
    "repair1":         {"mode": "single", "repair": True},
    "repair1_fewshot": {"mode": "single", "repair": True, "fewshot": True},
    "prune_repair1":   {"mode": "single", "repair": True, "prune": True},
    "vote3":           {"mode": "vote", "repair": True},
    "route_big":       {"mode": "route", "repair": True},
    "route_big_u":     {"mode": "route", "repair": True, "escalate_below": 3},
    "route_kimi":      {"mode": "route", "repair": True, "big_model": H.KIMI, "max_rows": 100},
}


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


def load_test():
    """Read TEST_HASH and test.jsonl fresh; refuse to run if they disagree (a rebuild may be mid-write)."""
    for _ in range(6):
        want = open(os.path.join(CYPHER_DIR, "data", "TEST_HASH")).read().split()[0]
        raw = open(os.path.join(CYPHER_DIR, "data", "test.jsonl"), "rb").read()
        got = hashlib.sha256(raw).hexdigest()
        if got == want:
            return [json.loads(l) for l in raw.decode().splitlines() if l.strip()], got
        print(f"test.jsonl sha {got[:12]} != TEST_HASH {want[:12]}; waiting for the rebuild to settle")
        time.sleep(20)
    sys.exit("test set hash mismatch; not running")


def pct(xs, p):
    s = sorted(xs)
    return s[int(p * (len(s) - 1))] if s else 0.0


def run_row(ex, cfg, budget, train):
    t0 = time.time()
    agreement, escalated = None, False
    if cfg["mode"] == "single":
        att = H.generate_and_repair(ex, cfg, budget, temperature=0.0, train=train)
        atts, chosen = [att], 0
    else:
        v = (H.vote3 if cfg["mode"] == "vote" else H.route)(ex, cfg, budget, train)
        atts, chosen, agreement = v["attempts"], v["chosen"], v["agreement"]
        escalated = v.get("escalated", False)
    final = atts[chosen]
    res = final["result"]
    gated = cfg.get("gate") and bool(final["problems"])
    gold = {"ok": True, **ex["gold_result"]}
    ungated_status = score(gold, res, ex["cypher"])
    if gated:  # validate_only: anything the validator rejects is counted invalid, whatever it would have returned
        status, lenient = "invalid", "invalid"
    else:
        status, lenient = ungated_status, score_lenient(gold, res, ex["cypher"])
    # agreement-group correctness for calibration
    return {
        "id": ex["id"], "graph": ex["graph"], "tier": ex["complexity"]["tier"], "question": ex["question"],
        "gold_cypher": ex["cypher"], "pred_cypher": final["cypher"], "validation_problems": final["problems"],
        "exec_status": status, "lenient_status": lenient, "ungated_status": ungated_status,
        "correct": status == "correct", "pred": status, "label": "correct",
        "exec_error": res.get("error"), "pred_n_rows": len(res["rows"]), "pred_rows_head": res["rows"][:3],
        "attempts": sum(a["calls"] for a in atts), "n_attempt_chains": len(atts),
        "attempt_statuses": [a["statuses"] for a in atts], "repaired": [a["repaired"] for a in atts],
        "attempt_models": [a["model"].split("/")[-1] for a in atts],
        "attempt_scores": [score(gold, a["result"], ex["cypher"]) for a in atts],
        "agreement": agreement, "escalated": escalated, "pruned": atts[0]["pruned"],
        "first_in_tokens": atts[0]["first_in_tokens"],
        "in_tokens": sum(a["in"] for a in atts), "out_tokens": sum(a["out"] for a in atts),
        "latency": round(time.time() - t0, 3), "api_error": next((a["api_error"] for a in atts if a["api_error"]), None),
        "truncated": any(a["truncated"] for a in atts),
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", required=True, choices=sorted(CONFIGS))
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--workers", type=int, default=8)
    ap.add_argument("--seed", type=int, default=0, help="label only; vote configs sample at T=0.7")
    ap.add_argument("--reasoning", default="low", help="low | medium | high | default (parameter not sent)")
    args = ap.parse_args()
    cfg = dict(CONFIGS[args.config], reasoning=None if args.reasoning == "default" else args.reasoning)

    examples, sha = load_test()
    lim = args.limit or cfg.get("max_rows", 0)
    if lim:
        examples = examples[:lim]
    train = [json.loads(l) for l in open(os.path.join(CYPHER_DIR, "data", "train.jsonl")) if l.strip()]
    start = ledger_total()
    if start >= CAP_USD:
        sys.exit(f"ledger at ${start:.2f} >= cap ${CAP_USD}")
    budget = H.Budget(start, CAP_USD)

    done = [0]
    lock = threading.Lock()

    def one(ex):
        try:
            r = run_row(ex, cfg, budget, train)
        except H.BudgetExceeded:
            return None
        with lock:
            done[0] += 1
            if done[0] % 25 == 0:
                print(f"  {done[0]}/{len(examples)} spent ${budget.spent():.3f}", flush=True)
        return r

    with ThreadPoolExecutor(args.workers) as pool:
        rows = [r for r in pool.map(one, examples) if r is not None]
    tag = args.config + ("" if args.reasoning == "low" else f"_r{args.reasoning}") + (f"_s{args.seed}" if args.seed else "")
    for m, (tin, tout, c) in budget.by_model.items():
        ledger_add(m, tin, tout, c, f"harness {tag} n={len(rows)}")
    n = len(rows)
    cost = budget.spent()
    cnt = lambda s: sum(r["exec_status"] == s for r in rows)
    lats = [r["latency"] for r in rows]

    def breakdown(key):
        out = {}
        for k in sorted({str(r[key]) for r in rows}):
            rs = [r for r in rows if str(r[key]) == k]
            out[k] = {"n": len(rs), "accuracy": round(sum(r["correct"] for r in rs) / len(rs), 4),
                      "accuracy_lenient": round(sum(r["lenient_status"] == "correct" for r in rs) / len(rs), 4),
                      "error": sum(r["exec_status"] in ("error", "invalid") for r in rs),
                      "empty": sum(r["exec_status"] == "empty" for r in rs)}
        return out

    summary = {
        "model": H.SMALL, "prompt": f"harness_{tag}", "config": args.config, "config_detail": cfg, "seed": args.seed,
        "mock": False, "n": n,
        "accuracy": round(cnt("correct") / n, 4),
        "accuracy_lenient": round(sum(r["lenient_status"] == "correct" for r in rows) / n, 4),
        "accuracy_ungated": round(sum(r["ungated_status"] == "correct" for r in rows) / n, 4),
        "invalid_outputs": cnt("error") + cnt("invalid"), "invalid_by_validator": cnt("invalid"),
        "error_rate": round((cnt("error") + cnt("invalid")) / n, 4), "empty_rate": round(cnt("empty") / n, 4),
        "wrong_rate": round(cnt("wrong") / n, 4),
        "p50_latency_s": round(statistics.median(lats), 3), "p95_latency_s": round(pct(lats, 0.95), 3),
        "cost_per_1k_requests_usd": round(cost / n * 1000, 4), "cost_total_usd": round(cost, 4),
        "cost_by_model": {m.split("/")[-1]: round(v[2], 4) for m, v in budget.by_model.items()},
        "in_tokens": sum(r["in_tokens"] for r in rows), "out_tokens": sum(r["out_tokens"] for r in rows),
        "first_call_in_tokens": sum(r["first_in_tokens"] for r in rows),
        "calls_per_row": round(sum(r["attempts"] for r in rows) / n, 3),
        "repair_rate": round(sum(any(x) for x in (r["repaired"] for r in rows)) / n, 4),
        "escalation_rate": round(sum(r["escalated"] for r in rows) / n, 4),
        "agreement_counts": {str(k): sum(r["agreement"] == k for r in rows) for k in (3, 2, 1)} if cfg["mode"] != "single" else None,
        "api_errors": sum(1 for r in rows if r["api_error"]), "truncated": sum(r["truncated"] for r in rows),
        "reasoning_effort": args.reasoning, "test_sha256": sha,
        "by_graph": breakdown("graph"), "by_tier": breakdown("tier"),
        "rows": rows,
    }
    out = os.path.join(CYPHER_DIR, "results", f"harness_{tag}.json")
    json.dump(summary, open(out, "w"), indent=1, default=str)
    print(f"{tag}: acc {summary['accuracy']:.1%} (ungated {summary['accuracy_ungated']:.1%}) lenient {summary['accuracy_lenient']:.1%} "
          f"err {summary['error_rate']:.1%} empty {summary['empty_rate']:.1%} p50 {summary['p50_latency_s']}s "
          f"p95 {summary['p95_latency_s']}s ${summary['cost_per_1k_requests_usd']}/1k calls/row {summary['calls_per_row']} "
          f"esc {summary['escalation_rate']:.1%} agree {summary['agreement_counts']} apierr {summary['api_errors']} | ledger ${ledger_total():.3f}")
    print("saved", out)


if __name__ == "__main__":
    main()
