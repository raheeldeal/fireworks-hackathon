"""Build data/test.jsonl (locked, from Spider dev) and data/train.jsonl (from Spider train).
Reproducible: fixed seed, deterministic ordering. Rows whose gold SQL fails or times out are dropped."""
import json, random, sqlite3, sys, os, hashlib
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from schema_util import load_tables, schema_text, approx_tokens
from score import execute_sql

ROOT = "raw/zip/spider_data"
T = load_tables(f"{ROOT}/tables.json")

def db_path(db):
    return f"{ROOT}/database/{db}/{db}.sqlite"

def gold_ok(db, sql):
    res = execute_sql(db_path(db), sql, timeout=5)
    return res["ok"] and res["rows"] is not None

def make_rows(src, prefix):
    out = []
    for i, r in enumerate(src):
        out.append({
            "id": f"{prefix}{i:04d}",
            "db_id": r["db_id"],
            "question": r["question"],
            "gold_sql": r["query"].strip().rstrip(";"),
            "schema": schema_text(T[r["db_id"]]),
        })
    return out

def main():
    rng = random.Random(20261101)
    dev = json.load(open(f"{ROOT}/dev.json"))
    rows = make_rows(dev, "dev")
    by_db = {}
    for r in rows:
        by_db.setdefault(r["db_id"], []).append(r)
    for db in by_db:
        rng.shuffle(by_db[db])
    # round-robin across DBs until 180 rows, so every schema is represented
    test, idx = [], {db: 0 for db in by_db}
    dbs = sorted(by_db)
    while len(test) < 180:
        progressed = False
        for db in dbs:
            if len(test) >= 180:
                break
            while idx[db] < len(by_db[db]):
                cand = by_db[db][idx[db]]; idx[db] += 1
                if gold_ok(db, cand["gold_sql"]):
                    test.append(cand); progressed = True; break
        if not progressed:
            break
    test.sort(key=lambda r: r["id"])
    os.makedirs("data", exist_ok=True)
    with open("data/test.jsonl", "w") as f:
        for r in test:
            f.write(json.dumps(r) + "\n")
    print("test rows", len(test), "dbs", len({r['db_id'] for r in test}))

    # train: Spider train split, different databases from dev by construction.
    tr = json.load(open(f"{ROOT}/train_spider.json")) if os.path.exists(f"{ROOT}/train_spider.json") else json.load(open("raw/spider_train_hf.json"))
    trows = make_rows(tr, "trn")
    trows = [r for r in trows if approx_tokens(r["schema"]) <= 450]
    rng.shuffle(trows)
    test_q = {r["question"].strip().lower() for r in test}
    train, per_db = [], {}
    for r in trows:
        if r["question"].strip().lower() in test_q or r["db_id"] in by_db:
            continue
        if per_db.get(r["db_id"], 0) >= 6:
            continue
        if not gold_ok(r["db_id"], r["gold_sql"]):
            continue
        train.append(r); per_db[r["db_id"]] = per_db.get(r["db_id"], 0) + 1
        if len(train) >= 450:
            break
    with open("data/train.jsonl", "w") as f:
        for r in train:
            f.write(json.dumps(r) + "\n")
    print("train rows", len(train), "dbs", len(per_db))

if __name__ == "__main__":
    main()
