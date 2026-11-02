"""Add lenient scores to existing results files by re-executing pred_cypher (no API calls)."""
import json, sys, os, logging
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from concurrent.futures import ThreadPoolExecutor
from executor import execute
from score import score, score_lenient
logging.getLogger("neo4j").setLevel(logging.ERROR)
test = {json.loads(l)["id"]: json.loads(l) for l in open("data/test.jsonl")}
for path in sys.argv[1:]:
    d = json.load(open(path))
    if "accuracy_lenient" in d:
        continue
    def fix(r):
        ex = test[r["id"]]
        res = execute(ex["graph"], r["pred_cypher"]) if r["pred_cypher"] else {"ok": False, "rows": [], "columns": [], "error": "no query"}
        gold = {"ok": True, **ex["gold_result"]}
        st = score(gold, res, ex["cypher"])
        if st != r["exec_status"]:
            print("  status drift", r["id"], r["exec_status"], "->", st)
        r["lenient_status"] = score_lenient(gold, res, ex["cypher"])
        r["pred_rows_head"] = res["rows"][:5]
        return r
    with ThreadPoolExecutor(8) as ex:
        d["rows"] = list(ex.map(fix, d["rows"]))
    n = d["n"]
    d["accuracy_lenient"] = round(sum(r["lenient_status"] == "correct" for r in d["rows"]) / n, 4)
    for key, field in (("by_graph", "graph"), ("by_tier", "tier")):
        for k, v in d[key].items():
            rs = [r for r in d["rows"] if r[field] == k]
            v["accuracy_lenient"] = round(sum(r["lenient_status"] == "correct" for r in rs) / len(rs), 4)
    json.dump(d, open(path, "w"), indent=1, default=str)
    print(path, "strict", d["accuracy"], "lenient", d["accuracy_lenient"])
