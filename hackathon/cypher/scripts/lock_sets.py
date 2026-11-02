"""Build data/test.jsonl (200, locked) and data/train.jsonl (500) from verified pools."""
import json, random, hashlib, collections
GRAPHS = ["movies", "recommendations", "northwind", "fincen", "twitter"]
def usable(r):
    return r["gold_ok"] and r["gold_n_rows"] > 0 and not r["gold_truncated"] and r["gold_result"] is not None and r["gold_secs"] < 8
def load(p):
    return [json.loads(l) for l in open(p)]
rng = random.Random(2026)
test_pool = [r for r in load("raw/pool_test.jsonl") if usable(r)]
train_pool = [r for r in load("raw/pool_train.jsonl") if usable(r)]
test = []
for g in GRAPHS:
    by = collections.defaultdict(list)
    for r in test_pool:
        if r["graph"] == g:
            by[r["complexity"]["tier"]].append(r)
    for t in by: rng.shuffle(by[t])
    hard = by["hard"][:10]
    med = by["medium"][:40 - len(hard) - 14]
    easy = by["easy"][:40 - len(hard) - len(med)]
    test += hard + med + easy
assert len(test) == 200, len(test)
rng.shuffle(test)
out = []
for i, r in enumerate(test):
    out.append({"id": f"t{i:03d}", "source_id": r["source_id"], "source_split": "hf_test", "graph": r["graph"],
                "question": r["question"], "cypher": r["cypher"], "schema": r["schema"], "data_source": r["data_source"],
                "complexity": r["complexity"], "gold_n_rows": r["gold_n_rows"], "gold_result": r["gold_result"]})
with open("data/test.jsonl", "w") as f:
    for r in out: f.write(json.dumps(r, sort_keys=True) + "\n")
h = hashlib.sha256(open("data/test.jsonl", "rb").read()).hexdigest()
open("data/TEST_HASH", "w").write(h + "  data/test.jsonl\n")
print("test sha256", h)
# train: same graphs, excluding any question or gold cypher in test
tq = {r["question"].strip().lower() for r in out}
tc = {" ".join(r["cypher"].split()).lower() for r in out}
cand = [r for r in train_pool if r["question"].strip().lower() not in tq and " ".join(r["cypher"].split()).lower() not in tc]
train = []
for g in GRAPHS:
    gs = [r for r in cand if r["graph"] == g]; rng.shuffle(gs); train += gs[:100]
rng.shuffle(train)
with open("data/train.jsonl", "w") as f:
    for i, r in enumerate(train):
        f.write(json.dumps({"id": f"tr{i:03d}", "source_id": r["source_id"], "source_split": "hf_train", "graph": r["graph"],
                            "question": r["question"], "cypher": r["cypher"], "schema": r["schema"],
                            "data_source": r["data_source"], "complexity": r["complexity"], "gold_n_rows": r["gold_n_rows"]}, sort_keys=True) + "\n")
print("train", len(train))
for name, rows in [("test", out), ("train", train)]:
    c = collections.Counter((r["graph"], r["complexity"]["tier"]) for r in rows)
    print(name, {g: [c[(g, t)] for t in ("easy", "medium", "hard")] for g in GRAPHS})
    print(" multi-hop or agg:", sum(r["complexity"]["multi_hop"] or r["complexity"]["aggregation"] for r in rows) / len(rows),
          "multi-hop:", sum(r["complexity"]["multi_hop"] for r in rows), "agg:", sum(r["complexity"]["aggregation"] for r in rows),
          "where:", sum(r["complexity"]["where"] for r in rows), "order/limit:", sum(r["complexity"]["order_by"] or r["complexity"]["limit"] for r in rows))
    print(" sources", collections.Counter(r["data_source"] for r in rows).most_common())
