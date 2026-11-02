#!/usr/bin/env python3
"""Run one question through the harness with tracing on, and print the trace.

    source ~/.zshrc                      # FIREWORKS_API_KEY, and the Langfuse keys if set
    cd hackathon/cypher/trace
    ../.venv/bin/python demo_run.py --question "Which actors played in the most genres?" --graph recommendations
    ../.venv/bin/python demo_run.py --from-test t000 --config route_big

Prints a step-by-step trace (step, what happened, tokens, latency), the final rows, and
the Langfuse trace URL. With --from-test the gold answer is known, so the trace also
carries a `correct` score.

Tracing is forced on for this script only (it sets CYPHER_TRACE_LOCAL before importing
the tracing module). It never changes how `harness/run_harness.py` behaves.
"""
import argparse, json, os, sys

os.environ.setdefault("CYPHER_TRACE_LOCAL", "1")   # local span tree, always available

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import instrument as I            # noqa: E402
import tracing as T              # noqa: E402


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--question", help="ad-hoc question in English")
    ap.add_argument("--graph", default="movies", help="movies | recommendations | northwind | fincen | twitter")
    ap.add_argument("--from-test", dest="from_test",
                    help="replay a locked test row by id (e.g. t000) so `correct` is scored")
    ap.add_argument("--config", default="route_big", choices=sorted(I.CONFIGS))
    ap.add_argument("--reasoning", default="low", help="low | medium | high | default")
    ap.add_argument("--model", help="override the small model (e.g. a fine-tuned checkpoint)")
    ap.add_argument("--session", help="Langfuse session id (default: demo_run_<config>_<time>)")
    ap.add_argument("--tag", action="append", default=[],
                    help="extra Langfuse trace tag; repeatable")
    ap.add_argument("--json", action="store_true", help="also print the span tree as JSON")
    args = ap.parse_args()

    if not args.question and not args.from_test:
        ap.error("give --question or --from-test")
    if "FIREWORKS_API_KEY" not in os.environ:
        sys.exit("FIREWORKS_API_KEY is not set. Run `source ~/.zshrc` first.")

    cfg = dict(I.CONFIGS[args.config],
               reasoning=None if args.reasoning == "default" else args.reasoning)
    if args.model:
        cfg["model"] = args.model
    rows = I.load_test()
    if args.from_test:
        ex = next((r for r in rows if r["id"] == args.from_test), None)
        if ex is None:
            sys.exit(f"no test row with id {args.from_test!r}")
    else:
        ex = I.adhoc_example(args.question, args.graph, rows)

    I.install()
    train = I.load_train() if cfg.get("fewshot") else None
    budget = I.new_budget()

    import time as _t
    session = args.session or f"demo_run_{args.config}_{_t.strftime('%H%M%S')}"

    print(I.status_line())
    print(f"config: {args.config}   graph: {ex['graph']}   tier: {(ex.get('complexity') or {}).get('tier')}")
    print(f"session: {session}" + (f"   tags: {', '.join(args.tag)}" if args.tag else ""))
    print(f"question: {ex['question']}\n")

    try:
        rec = I.run_one(ex, cfg, args.config, budget, train,
                        session_id=session, tags=args.tag)
    finally:
        I.record_spend(budget, f"demo_run {args.config} id={ex.get('id')}")
        T.flush()

    print("--- trace " + "-" * 60)
    print(T.render(rec["tree"]))
    print("--- result " + "-" * 59)
    print("cypher:\n" + (rec["cypher"] or "(none)"))
    print(f"\nstatus: {rec['status']}   rows: {rec['row_count']}")
    if rec["error"]:
        print(f"error: {rec['error']}")
    for r in rec["rows"][:10]:
        print("  " + json.dumps(r, default=str)[:200])
    if rec["row_count"] > 10:
        print(f"  ... {rec['row_count'] - 10} more")
    if rec["correct"] is not None:
        print(f"\ncorrect: {rec['correct']}   (lenient: {rec['correct_lenient']})")
        print("gold cypher:\n" + ex["cypher"].replace("\\n", "\n"))
    print(f"\ntokens in/out: {rec['in_tokens']}/{rec['out_tokens']}   "
          f"cost ${rec['cost_usd']:.5f}   latency {rec['latency_s']}s   "
          f"model calls {rec['model_calls']}")
    if rec["agreement"] is not None:
        print(f"vote agreement: {rec['agreement']}/3   escalated: {rec['escalated']}")
    print(f"\nledger: ${I.ledger_total():.4f} of ${I.CAP_USD:.2f} ({I.LEDGER})")
    if T.LOCAL_ON:
        print(f"local span tree: {T.LOCAL_DUMP_PATH}")
    print("langfuse trace: " + (rec["trace_url"] or
                                "(Langfuse off - set LANGFUSE_PUBLIC_KEY / LANGFUSE_SECRET_KEY; see SETUP.md)"))
    if args.json:
        print(json.dumps(rec["tree"], indent=1, default=str))


if __name__ == "__main__":
    main()
