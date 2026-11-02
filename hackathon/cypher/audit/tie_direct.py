import json, os, sys, collections
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from executor import execute
HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
test = {json.loads(l)["id"]: json.loads(l) for l in open(os.path.join(HERE, "data/test.jsonl"))}
ex = test["t000"]
print("GOLD CYPHER:\n", ex["cypher"], "\n")
# gold without the LIMIT line
q = "\n".join(l for l in ex["cypher"].splitlines() if not l.strip().upper().startswith("LIMIT"))
r = execute(ex["graph"], q)
rows = r.get("rows") if isinstance(r, dict) else None
print("rows without LIMIT:", len(rows) if rows else r)
if rows:
    key = [c for c in r["columns"] if isinstance(rows[0].get(c), (int, float))]
    kc = collections.Counter(tuple(x.get(c) for c in key) for x in rows)
    top = sorted(kc.items(), key=lambda kv: -(kv[0][0] or 0))[:3]
    print("top sort-key values and how many rows share them:", top)
    print("gold kept:", len(ex["gold_result"]["rows"]), "rows")
    print("=> ties at the cut:", top[0][1] > len(ex["gold_result"]["rows"]))
