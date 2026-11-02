"""Strict vs lenient accuracy for result files: how much of a gap is only "which columns to return"?

  python lenient.py results/r1_base.json results/r5_full.json results/r6_ft1.json

Strict = score.py (the headline everywhere). Lenient also accepts answers that contain every gold row's values plus
extra columns (score.covers_gold). Final queries are re-executed (no model calls); gold comes from data/test.jsonl.
"""
import json, os, sys
from concurrent.futures import ThreadPoolExecutor

import metrics
from executor import execute
from score import covers_gold

HERE = os.path.dirname(os.path.abspath(__file__))


def main(specs):
    gold = {r["id"]: r for r in (json.loads(l) for l in open(os.path.join(HERE, "data", "test.jsonl")))}
    for spec in specs:
        path, _, stage = spec.partition(":")
        doc = json.load(open(path))
        stage = stage or list(doc["views"])[-1]
        finals = [(r["id"], metrics.cut(r, stage)) for r in doc["rows"]]
        with ThreadPoolExecutor(8) as ex:
            results = list(ex.map(lambda f: execute(gold[f[0]]["graph"], f[1]["cypher"]) if f[1].get("cypher") else None, finals))
        strict = sum(c["outcome"] == "correct" for _, c in finals)
        lenient = sum(c["outcome"] == "correct" or (res is not None and covers_gold(gold[i]["gold_result"], res))
                      for (i, c), res in zip(finals, results))
        n = len(finals)
        print(f"{doc['tag'] + ':' + stage:<30} strict {strict / n:.1%}   lenient {lenient / n:.1%}   (+{(lenient - strict) / n:.1%})")


if __name__ == "__main__":
    main(sys.argv[1:])
