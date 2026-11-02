"""Build the verified training pool and split it into the disjoint sets each training recipe uses.

  python scripts/build_pool.py          # run from hackathon/cypher/; ~8k gold queries on the demo server

1. Take every train-split row for our 5 graphs from raw/ (the dataset's train split only).
2. Drop duplicate questions and anything whose question or gold query also appears in data/test.jsonl.
3. Run each gold query; keep it with the same "usable" rule lock_sets.py used for the test set.
4. Split, with a fixed seed, into:
     data/train_pool.jsonl   all usable rows                         -> FT1 (SFT on gold)
     data/harvest1.jsonl     1,500 rows                              -> trace harvest for FT2 / FT3
     data/harvest2.jsonl     1,000 different rows                    -> FT4 round 2
     data/rl_prompts.jsonl   400 rows not in either harvest set      -> FT6 (RL)
     data/dev.jsonl          200 rows in no other set                -> harness design choices (never the test set)

  python scripts/build_pool.py --other-graphs --per-graph 300   # FT-X: verified rows from 9 other graphs
     data/xgraph_pool.jsonl  same checks, other schemas; ids x00000...
"""
import argparse, collections, json, os, random, sys
from concurrent.futures import ThreadPoolExecutor

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, HERE)
from executor import GRAPHS, MAX_ROWS, execute  # noqa: E402
from score import complexity  # noqa: E402

# The dataset's other graphs that the demo server serves (checked 2026-11-02; eoflix refuses the login).
OTHER_GRAPHS = ["companies", "twitch", "grandstack", "gameofthrones", "buzzoverflow", "network", "offshoreleaks",
                "stackoverflow2", "bluesky"]


def norm_cypher(c):
    return " ".join(c.split()).lower()


def usable(res):
    """Same bar as the locked test set (scripts/lock_sets.py): runs, 1-200 rows, under 8 s."""
    return res["ok"] and 0 < len(res["rows"]) <= 200 and len(res["rows"]) < MAX_ROWS and res["secs"] < 8


def write(path, rows):
    with open(path, "w") as f:
        for r in rows:
            f.write(json.dumps(r, sort_keys=True, default=str) + "\n")
    print(f"{os.path.relpath(path, HERE)}: {len(rows)} rows")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--other-graphs", action="store_true",
                    help="instead: verify rows from the dataset's other graphs into data/xgraph_pool.jsonl (FT-X)")
    ap.add_argument("--per-graph", type=int, default=0, help="cap candidates per graph (0 = all)")
    args = ap.parse_args()
    graphs = OTHER_GRAPHS if args.other_graphs else GRAPHS

    test = [json.loads(l) for l in open(os.path.join(HERE, "data", "test.jsonl"))]
    test_q = {r["question"].strip().lower() for r in test}
    test_c = {norm_cypher(r["cypher"]) for r in test}

    raw = [json.loads(l) for l in open(os.path.join(HERE, "raw", "text2cypher-2024v1_train.jsonl"))]
    seen, cands, per_graph = set(), [], collections.Counter()
    for r in raw:
        alias = r["database_reference_alias"] or ""
        graph = alias.replace("neo4jlabs_demo_db_", "")
        q = r["question"].strip().lower()
        if graph not in graphs or q in seen or q in test_q or norm_cypher(r["cypher"]) in test_c:
            continue
        if args.per_graph and per_graph[graph] >= args.per_graph:
            continue
        seen.add(q)
        per_graph[graph] += 1
        cands.append({"graph": graph, "question": r["question"], "cypher": r["cypher"], "schema": r["schema"],
                      "data_source": r["data_source"], "source_id": r["instance_id"], "source_split": "hf_train"})
    print(f"{len(cands)} candidate train rows after dedupe and test-overlap removal")

    def run(r):
        return r, execute(r["graph"], r["cypher"])

    pool = []
    with ThreadPoolExecutor(8) as ex:
        for i, (r, res) in enumerate(ex.map(run, cands), 1):
            if usable(res):
                r["complexity"] = complexity(r["cypher"])
                r["gold_n_rows"] = len(res["rows"])
                r["gold_result"] = {"columns": res["columns"], "rows": res["rows"]}
                pool.append(r)
            if i % 500 == 0:
                print(f"  {i}/{len(cands)} checked, {len(pool)} usable", flush=True)

    random.Random(2026).shuffle(pool)
    for i, r in enumerate(pool):
        r["id"] = f"{'x' if args.other_graphs else 'p'}{i:05d}"
    print("usable by graph:", dict(collections.Counter(r["graph"] for r in pool)))
    if args.other_graphs:
        write(os.path.join(HERE, "data", "xgraph_pool.jsonl"), pool)
        return
    write(os.path.join(HERE, "data", "train_pool.jsonl"), pool)
    write(os.path.join(HERE, "data", "harvest1.jsonl"), pool[:1500])
    write(os.path.join(HERE, "data", "harvest2.jsonl"), pool[1500:2500])
    write(os.path.join(HERE, "data", "rl_prompts.jsonl"), pool[2500:2900])
    write(os.path.join(HERE, "data", "dev.jsonl"), pool[2900:3100])


if __name__ == "__main__":
    main()
