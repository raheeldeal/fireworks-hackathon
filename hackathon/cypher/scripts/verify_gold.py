"""Execute gold Cypher for candidate rows; write verified pools with results + complexity."""
import json, random, sys, os, logging
logging.getLogger("neo4j").setLevel(logging.ERROR)
from concurrent.futures import ThreadPoolExecutor
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from executor import execute, GRAPHS, MAX_ROWS
from score import complexity

split, per_graph, out = sys.argv[1], int(sys.argv[2]), sys.argv[3]
DS = os.environ.get("T2C_DS", "text2cypher-2025v1")
rows = [json.loads(l) for l in open(f"raw/{DS}_{split}.jsonl")]
rng = random.Random(42)
cands = []
for g in GRAPHS:
    rs = [r for r in rows if r["database_reference_alias"] == f"neo4jlabs_demo_db_{g}"]
    seen, uniq = set(), []
    for r in rs:
        q = r["question"].strip().lower()
        if q not in seen:
            seen.add(q); uniq.append(r)
    rng.shuffle(uniq)
    for r in uniq[:per_graph]:
        r["graph"] = g
        cands.append(r)

def run(r):
    res = execute(r["graph"], r["cypher"])
    return r, res

n = 0
with open(out, "w") as f, ThreadPoolExecutor(8) as ex:
    for r, res in ex.map(run, cands):
        n += 1
        rec = {"source_id": r["instance_id"], "source_split": split, "graph": r["graph"], "question": r["question"],
               "cypher": r["cypher"], "schema": r["schema"], "data_source": r["data_source"],
               "complexity": complexity(r["cypher"]), "gold_ok": res["ok"], "gold_error": res["error"],
               "gold_n_rows": len(res["rows"]), "gold_secs": res["secs"],
               "gold_truncated": len(res["rows"]) >= MAX_ROWS,
               "gold_result": {"columns": res["columns"], "rows": res["rows"]} if res["ok"] and len(res["rows"]) <= 200 else None}
        f.write(json.dumps(rec, default=str) + "\n")
        if n % 50 == 0:
            print(n, "done", flush=True)
