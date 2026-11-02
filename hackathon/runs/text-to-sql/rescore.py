#!/usr/bin/env python3
"""Secondary, lenient execution metric: same rows as the gold ignoring column order (gold projection order is often
arbitrary in Spider, e.g. "count(*), name" vs "name, count(*)"). Strict exec accuracy stays the primary number.
Usage: python3 rescore.py results/*.json"""
import json, os, sys, re
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
from score import execute_sql
from collections import Counter
DB = os.path.join(HERE, "raw", "zip", "spider_data", "database")
def lenient(pred, gold, db):
    p, g = execute_sql(db, pred), execute_sql(db, gold)
    if not (p["ok"] and g["ok"]): return False
    if p["rows"] == g["rows"] or Counter(p["rows"]) == Counter(g["rows"]): return True
    if not p["rows"] or not g["rows"] or len(p["rows"][0]) != len(g["rows"][0]): return False
    cols = lambda rows: sorted(tuple(sorted(Counter(repr(r[i]) for r in rows).items())) for i in range(len(rows[0])))
    return cols(p["rows"]) == cols(g["rows"])
for path in sys.argv[1:]:
    d = json.load(open(path))
    ok = sum(lenient(r["pred_sql"], r["gold_sql"], os.path.join(DB, r["db_id"], r["db_id"] + ".sqlite")) for r in d["rows"])
    d["lenient_accuracy"] = round(ok / d["n"], 4)
    json.dump(d, open(path, "w"), indent=1)
    print(f"{os.path.basename(path):55s} strict {d['accuracy']:.1%}  lenient {d['lenient_accuracy']:.1%}")
