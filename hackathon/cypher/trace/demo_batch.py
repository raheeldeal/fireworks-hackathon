#!/usr/bin/env python3
"""Trace a slice of the locked test set so the Langfuse dashboard has content for judges.

    source ~/.zshrc
    cd hackathon/cypher/trace
    ../.venv/bin/python demo_batch.py --config route_big --limit 20

One root trace per question, tagged graph / tier / config, grouped into one Langfuse
session. Each trace carries three numeric scores: `correct` (0 or 1), `latency_s` and
`cost_usd`. Writes trace/last_batch.json (every span tree) and trace/batch_summary.json.

Reads data/test.jsonl; never writes it. Spend is capped by trace/ledger.csv ($1).
"""
import argparse, json, os, statistics, sys, threading, time
from concurrent.futures import ThreadPoolExecutor

os.environ.setdefault("CYPHER_TRACE_LOCAL", "1")

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import instrument as I            # noqa: E402
import tracing as T              # noqa: E402

BATCH_JSON = os.path.join(HERE, "last_batch.json")
SUMMARY_JSON = os.path.join(HERE, "batch_summary.json")


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--config", default="route_big", choices=sorted(I.CONFIGS))
    ap.add_argument("--limit", type=int, default=20)
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--reasoning", default="low")
    ap.add_argument("--spread", action="store_true",
                    help="spread the slice across graphs and tiers instead of taking the first N")
    ap.add_argument("--session", default=None, help="Langfuse session id (default: demo_batch_<ts>)")
    args = ap.parse_args()

    if "FIREWORKS_API_KEY" not in os.environ:
        sys.exit("FIREWORKS_API_KEY is not set. Run `source ~/.zshrc` first.")

    cfg = dict(I.CONFIGS[args.config],
               reasoning=None if args.reasoning == "default" else args.reasoning)
    rows = I.load_test()
    if args.spread:
        rows = sorted(rows, key=lambda r: (r["graph"], r["complexity"]["tier"]))
        step = max(1, len(rows) // max(1, args.limit))
        rows = rows[::step]
    examples = rows[:args.limit]

    I.install()
    train = I.load_train() if cfg.get("fewshot") else None
    budget = I.new_budget()
    session = args.session or f"demo_batch_{args.config}_{time.strftime('%H%M%S')}"

    print(I.status_line())
    print(f"config {args.config}  rows {len(examples)}  workers {args.workers}  session {session}")

    out, lock, t0 = [], threading.Lock(), time.time()

    def one(ex):
        try:
            rec = I.run_one(ex, cfg, args.config, budget, train, session_id=session)
        except I.H.BudgetExceeded:
            print(f"  {ex['id']}: budget cap reached, stopping")
            return None
        except Exception as e:  # noqa: BLE001  one bad row must not sink the batch
            print(f"  {ex['id']}: {type(e).__name__}: {e}")
            return None
        with lock:
            out.append(rec)
            mark = "ok " if rec["correct"] else ("-  " if rec["correct"] is False else "?  ")
            print(f"  {mark}{rec['id']} {rec['graph']:<15} {rec['tier']:<6} "
                  f"{rec['status']:<5} {rec['row_count']:>4} rows  "
                  f"{rec['latency_s']:>6.1f}s  ${rec['cost_usd']:.5f}"
                  + (f"  agree {rec['agreement']}/3" if rec["agreement"] else "")
                  + ("  escalated" if rec["escalated"] else ""), flush=True)
        return rec

    try:
        with ThreadPoolExecutor(args.workers) as pool:
            list(pool.map(one, examples))
    finally:
        I.record_spend(budget, f"demo_batch {args.config} n={len(out)}")
        T.flush()

    if not out:
        sys.exit("no rows completed")
    scored = [r for r in out if r["correct"] is not None]
    summary = {
        "config": args.config, "session": session, "n": len(out),
        "accuracy": round(sum(r["correct"] for r in scored) / len(scored), 4) if scored else None,
        "accuracy_lenient": round(sum(r["correct_lenient"] for r in scored) / len(scored), 4) if scored else None,
        "error_rate": round(sum(r["status"] == "error" for r in out) / len(out), 4),
        "empty_rate": round(sum(r["status"] == "empty" for r in out) / len(out), 4),
        "p50_latency_s": round(statistics.median(r["latency_s"] for r in out), 3),
        "cost_total_usd": round(sum(r["cost_usd"] for r in out), 5),
        "cost_per_question_usd": round(sum(r["cost_usd"] for r in out) / len(out), 6),
        "in_tokens": sum(r["in_tokens"] for r in out),
        "out_tokens": sum(r["out_tokens"] for r in out),
        "escalation_rate": round(sum(bool(r["escalated"]) for r in out) / len(out), 4),
        "wall_seconds": round(time.time() - t0, 1),
        "langfuse": T.LANGFUSE_ON,
        "trace_urls": [r["trace_url"] for r in out if r["trace_url"]],
        "rows": [{k: v for k, v in r.items() if k not in ("tree", "rows")} for r in out],
    }
    json.dump(summary, open(SUMMARY_JSON, "w"), indent=1, default=str)
    T.dump_all(BATCH_JSON)

    print(f"\n{len(out)} traced  acc {summary['accuracy']}  lenient {summary['accuracy_lenient']}  "
          f"err {summary['error_rate']}  empty {summary['empty_rate']}  "
          f"p50 {summary['p50_latency_s']}s  total ${summary['cost_total_usd']}  "
          f"wall {summary['wall_seconds']}s")
    print(f"ledger: ${I.ledger_total():.4f} of ${I.CAP_USD:.2f}")
    print("summary: " + SUMMARY_JSON)
    if T.LOCAL_ON:
        print("span trees: " + BATCH_JSON)
    if T.LANGFUSE_ON:
        host = os.environ.get("LANGFUSE_HOST", "https://cloud.langfuse.com")
        print(f"dashboard: {host} -> Tracing -> Sessions -> {session}")
        if summary["trace_urls"]:
            print("one trace: " + summary["trace_urls"][0])
    else:
        print("Langfuse off: no dashboard content was created. See SETUP.md for the keys.")


if __name__ == "__main__":
    main()
