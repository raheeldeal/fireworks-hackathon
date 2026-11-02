"""Run one harness config over a question file, grade every attempt, and write results/<tag>.json.

  python run_eval.py --tag r1_base --model muse-glimmer-30b
  python run_eval.py --tag r5_full --model muse-glimmer-30b --shots 3 --fix --repair 3 --escalate kimi-k3
  python run_eval.py --tag harvest1 --data data/train_pool.jsonl --split train ...   # traces for training

The result file holds one summary per stage the config enabled ("views"): a full-harness run yields the R2-R5 rows.
"""
import argparse, json, os, sys, time
from concurrent.futures import ThreadPoolExecutor

import fw, metrics
from executor import execute
from harness import Config, Harness
from retrieve import EmbeddingRetriever, Retriever
from score import score
from tracing import Tracer

HERE = os.path.dirname(os.path.abspath(__file__))


def load_env(path=os.path.join(HERE, ".env")):
    """KEY="value" lines from the git-ignored .env; values already in the environment win."""
    if os.path.exists(path):
        for line in open(path):
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip().strip('"'))


def load_jsonl(path):
    return [json.loads(l) for l in open(path) if l.strip()]


def grade(row, attempts):
    """Score every attempt against gold. Gold is used only here, after the harness has finished."""
    gold = row.get("gold_result") or execute(row["graph"], row["cypher"])  # train rows don't store gold rows
    for a in attempts:
        res = a.pop("_result")
        a["outcome"] = score(gold, res, row["cypher"])
        a["preview"] = res["rows"][:3]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--tag", required=True)
    ap.add_argument("--model", default="muse-glimmer-30b")
    ap.add_argument("--model-path", help="fine-tuned checkpoint for the training sampler")
    ap.add_argument("--shots", type=int, default=0)
    ap.add_argument("--fix", action="store_true")
    ap.add_argument("--repair", type=int, default=0)
    ap.add_argument("--escalate")
    ap.add_argument("--warn", action="store_true", help="repair queries that ran with database warnings")
    # kimi-k3 reasons before answering: at 400 tokens it can return nothing (seen in smoke10), so give it room
    ap.add_argument("--escalate-effort", default="low", help="reasoning_effort for the escalation model")
    ap.add_argument("--escalate-max-tokens", type=int, default=2048)
    ap.add_argument("--data", default=os.path.join(HERE, "data", "test.jsonl"))
    ap.add_argument("--examples", default=os.path.join(HERE, "data", "train.jsonl"), help="pool for --shots")
    ap.add_argument("--retriever", default="keyword", choices=["keyword", "embed"], help="how --shots examples are ranked")
    ap.add_argument("--split", default="test", choices=["test", "train"])
    ap.add_argument("--limit", type=int)
    ap.add_argument("--workers", type=int, default=6)
    ap.add_argument("--max-tokens", type=int, default=400)
    ap.add_argument("--effort", help="reasoning_effort for a serverless main model (e.g. a teacher)")
    ap.add_argument("--no-trace", action="store_true")
    args = ap.parse_args()
    load_env()

    cfg = Config(shots=args.shots, fix=args.fix, repair=args.repair, escalate=args.escalate, warn=args.warn)
    rows = load_jsonl(args.data)[: args.limit]
    llm = fw.make_llm(args.model, args.model_path, max_tokens=args.max_tokens, note=args.tag,
                      extra={"reasoning_effort": args.effort} if args.effort else None)
    esc = fw.make_llm(args.escalate, max_tokens=args.escalate_max_tokens, extra={"reasoning_effort": args.escalate_effort},
                      note=args.tag + " escalate") if args.escalate else None
    pool = load_jsonl(args.examples)
    retriever = (EmbeddingRetriever(pool, [r["question"] for r in rows]) if args.retriever == "embed" else Retriever(pool))
    harness = Harness(cfg, llm, esc, retriever, Tracer(enabled=not args.no_trace))
    print(f"{args.tag}: {len(rows)} rows, model {llm.name}, config {cfg.as_dict()}, ledger ${fw.spent():.2f}")

    def one(row):
        t0 = time.time()
        with harness.tracer.question(row, args.tag, args.split, cfg.as_dict()) as root:
            try:
                attempts, example_ids = harness.solve(row, exclude_ids={row["id"]})
                grade(row, attempts)
                error = None
            except fw.CapReached:
                raise
            except Exception as e:  # one bad row must not kill the run; it is recorded as an error
                attempts, example_ids, error = [], [], f"{type(e).__name__}: {str(e)[:300]}"
            out = {"id": row["id"], "graph": row["graph"], "tier": row["complexity"]["tier"],
                   "question": row["question"], "gold_cypher": row["cypher"], "examples": example_ids,
                   "attempts": attempts, "harness_error": error, "wall_secs": round(time.time() - t0, 3),
                   "outcome": "error", "langfuse_trace_id": root.trace_id}
            final = metrics.cut(out, metrics.STAGES[-1])
            out.update(outcome=final["outcome"], final_cypher=final.get("cypher"), stage=final["stage"])
            final_attempt = next((a for a in reversed(attempts) if a["cypher"] == out["final_cypher"]), None)
            root.update(output={"cypher": out["final_cypher"], "outcome": out["outcome"], "stage": out["stage"],
                                "rows": final_attempt["preview"] if final_attempt else []})
            root.score_trace(name="correct", value=1.0 if out["outcome"] == "correct" else 0.0, data_type="NUMERIC")
            root.score_trace(name="outcome", value=out["outcome"], data_type="CATEGORICAL")
        return out

    results = []
    with ThreadPoolExecutor(args.workers) as pool:
        for i, out in enumerate(pool.map(one, rows), 1):
            results.append(out)
            if i % 20 == 0 or i == len(rows):
                ok = sum(r["outcome"] == "correct" for r in results)
                print(f"  {i}/{len(rows)}  correct {ok}  ledger ${fw.spent():.2f}", flush=True)
    harness.tracer.flush()

    enabled = ["first"] + (["fix"] if cfg.fix else []) + (["repair"] if cfg.repair else []) + \
              (["escalate"] if cfg.escalate else [])
    views = {s: metrics.summarize(results, s) for s in enabled}
    doc = {"tag": args.tag, "split": args.split, "data": os.path.relpath(args.data, HERE), "model": llm.name,
           "retriever": args.retriever, "shots": args.shots,
           "escalate_model": esc.name if esc else None, "config": cfg.as_dict(),
           "created": time.strftime("%Y-%m-%dT%H:%M:%S"), "summary": views[enabled[-1]], "views": views,
           "rows": results}
    os.makedirs(os.path.join(HERE, "results"), exist_ok=True)
    path = os.path.join(HERE, "results", f"{args.tag}.json")
    json.dump(doc, open(path, "w"), indent=1, default=str)

    print(f"\n{'stage':<10}{'acc':>8}{'95% CI':>18}{'$/question':>13}{'calls/q':>9}{'p50 s':>8}")
    for s, v in views.items():
        print(f"{s:<10}{v['accuracy']:>8.1%}{str(v['ci95']):>18}{v['cost_per_question']:>13.5f}"
              f"{v['calls_per_question']:>9.2f}{v['p50_secs']:>8.2f}")
    print(f"wrote {os.path.relpath(path, HERE)}; ledger ${fw.spent():.2f} of ${fw.CAP:.2f}")


if __name__ == "__main__":
    sys.exit(main())
