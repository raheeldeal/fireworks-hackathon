"""Append the rows each query returned to traces logged before rows were traced (results/*.json).

  python scripts/backfill_rows.py results/r6_ft1.json results/r5_full.json ...   # run from hackathon/cypher/

Langfuse traces can't be rewritten, so this adds one "rows (<source>)" step per attempt to the existing trace
(same trace id), holding the status, row count and the first rows saved in the result file, plus the gold rows.
Rows come from the local result files: no model or database calls.
"""
import json, os, sys

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, HERE)
from run_eval import load_env  # noqa: E402


def main(paths):
    load_env()
    from langfuse import Langfuse
    lf = Langfuse(public_key=os.environ["LANGFUSE_PUBLIC_KEY"], secret_key=os.environ["LANGFUSE_SECRET_KEY"],
                  base_url=os.environ.get("LANGFUSE_BASE_URL"))
    gold = {r["id"]: r for r in (json.loads(l) for l in open(os.path.join(HERE, "data", "test.jsonl")))}
    for path in paths:
        doc, n = json.load(open(path)), 0
        for row in doc["rows"]:
            if not row.get("langfuse_trace_id"):
                continue
            ctx = {"trace_id": row["langfuse_trace_id"]}
            for a in row["attempts"]:
                obs = lf.start_observation(trace_context=ctx, name=f"rows ({a['source']})", as_type="span",
                                           input=a["cypher"],
                                           output={"status": a["status"], "outcome": a.get("outcome"),
                                                   "n_rows": a["n_rows"], "rows": a.get("preview", [])})
                obs.end()
                n += 1
            if row["id"] in gold:
                lf.start_observation(trace_context=ctx, name="gold rows", as_type="span", input=row["gold_cypher"],
                                     output={"rows": gold[row["id"]]["gold_result"]["rows"][:5]}).end()
                n += 1
        lf.flush()
        print(f"{doc['tag']}: added {n} row steps to {len(doc['rows'])} traces")


if __name__ == "__main__":
    main(sys.argv[1:])
