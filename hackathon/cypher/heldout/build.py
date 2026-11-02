"""Build heldout/test_<graph>.jsonl from the 2025v1 TEST split for one graph not in the main five.
Same filter as scripts/lock_sets.py: gold runs, 1..200 rows, <8 s. Stratify 25 hard / 40 medium / 35 easy (main set's 10/16/14 per 40),
filling shortfalls from the other tiers. Also caches strip_limit(gold) results for score_v2's LIMIT rule."""
import json, random, hashlib, collections, sys, os, logging
from concurrent.futures import ThreadPoolExecutor
HERE = os.path.dirname(os.path.abspath(__file__)); CY = os.path.dirname(HERE)
sys.path.insert(0, CY)
from executor import execute
from score import complexity, strip_limit
logging.getLogger("neo4j").setLevel(logging.ERROR)
G = sys.argv[1]
raw = [json.loads(l) for l in open(os.path.join(CY, "raw", "text2cypher-2025v1_test.jsonl"))]
rows = [r for r in raw if r.get("database_reference_alias") == f"neo4jlabs_demo_db_{G}"]
print(G, "raw rows", len(rows))
res = list(ThreadPoolExecutor(8).map(lambda r: execute(G, r["cypher"]), rows))
pool = []
for r, x in zip(rows, res):
    if x["ok"] and 1 <= len(x["rows"]) <= 200 and x["secs"] < 8:
        pool.append((r, x))
print("usable", len(pool), "fail", sum(not x["ok"] for x in res), "empty", sum(x["ok"] and not x["rows"] for x in res), ">200", sum(len(x["rows"]) > 200 for x in res))
rng = random.Random(2026)
by = collections.defaultdict(list)
for r, x in pool:
    by[complexity(r["cypher"])["tier"]].append((r, x))
for t in by: rng.shuffle(by[t])
want = {"hard": 25, "medium": 40, "easy": 35}
pick = {t: by[t][:want[t]] for t in want}
short = 100 - sum(len(v) for v in pick.values())
for t in ("medium", "hard", "easy"):
    extra = by[t][len(pick[t]):len(pick[t]) + short]; pick[t] += extra; short -= len(extra)
test = [p for t in want for p in pick[t]]
rng.shuffle(test)
out = []
for i, (r, x) in enumerate(test):
    out.append({"id": f"h{i:03d}", "source_id": r["instance_id"], "source_split": "hf_test", "source_dataset": "neo4j/text2cypher-2025v1",
                "graph": G, "question": r["question"], "cypher": r["cypher"], "schema": r["schema"], "data_source": r["data_source"],
                "complexity": complexity(r["cypher"]), "gold_n_rows": len(x["rows"]), "gold_result": {"columns": x["columns"], "rows": x["rows"]}})
p = os.path.join(HERE, f"test_{G}.jsonl")
with open(p, "w") as f:
    for r in out: f.write(json.dumps(r, sort_keys=True, default=str) + "\n")
h = hashlib.sha256(open(p, "rb").read()).hexdigest()
open(os.path.join(HERE, "HASH"), "w").write(f"{h}  heldout/test_{G}.jsonl\n")
unl = {}
for r in out:
    if r["complexity"]["limit"]:
        x = execute(G, strip_limit(r["cypher"]))
        unl[r["id"]] = {"ok": x["ok"], "rows": x["rows"], "columns": x["columns"]}
json.dump(unl, open(os.path.join(HERE, f"gold_unlimited_{G}.json"), "w"), default=str)
print("n", len(out), collections.Counter(r["complexity"]["tier"] for r in out), "sha256", h)
# gold sanity: v2 of gold vs itself
