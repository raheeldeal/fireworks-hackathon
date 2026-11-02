#!/usr/bin/env python3
"""Eval-of-evals: audit every runs/<task>/data/test.jsonl.
Reports size, duplicate inputs, label coverage and balance, input length spread, and a label-noise
estimate = rows that EVERY model config missed (if all models fail the same row, the label is suspect)."""
import glob, json, os, statistics, sys
from collections import Counter

root = sys.argv[1] if len(sys.argv) > 1 else "."
def text_of(r):
    for f in ("text", "input", "question", "prompt", "query", "description", "note", "transcript"):
        if f in r: return str(r[f])
    return json.dumps(r)
def label_of(r):
    for f in ("label", "gold", "intent", "answer", "sql", "expected"):
        if f in r: return json.dumps(r[f], sort_keys=True) if not isinstance(r[f], str) else r[f]
    return None

print(f"{'task':18s} {'rows':>5s} {'dups':>4s} {'labels':>6s} {'min/cls':>7s} {'len p50':>7s} {'len p90':>7s} {'all-miss':>8s} {'configs':>7s}")
for test in sorted(glob.glob(os.path.join(root, "*", "data", "test.jsonl"))):
    task = test.split(os.sep)[-3]
    rows = [json.loads(l) for l in open(test) if l.strip()]
    texts = [text_of(r) for r in rows]
    dups = len(texts) - len(set(t.strip().lower() for t in texts))
    labels = [label_of(r) for r in rows]
    c = Counter(l for l in labels if l is not None)
    lens = sorted(len(t.split()) for t in texts)
    p50 = lens[len(lens)//2]; p90 = lens[int(0.9*(len(lens)-1))]
    # shared misses across all per-row result files with >=100 rows
    miss_sets, n_cfg = [], 0
    for p in glob.glob(os.path.join(root, task, "results", "*.json")):
        try: d = json.load(open(p))
        except Exception: continue
        rr = d.get("rows") if isinstance(d, dict) else None
        if not rr or len(rr) < 100 or "correct" not in rr[0]: continue
        miss_sets.append({r.get("id") for r in rr if not r.get("correct")}); n_cfg += 1
    allmiss = len(set.intersection(*miss_sets)) if miss_sets else -1
    print(f"{task:18s} {len(rows):5d} {dups:4d} {len(c):6d} {min(c.values()) if c else 0:7d} {p50:7d} {p90:7d} {allmiss:8d} {n_cfg:7d}")
print("\nall-miss = rows every scored config got wrong (label-noise ceiling estimate). min/cls = rows in the rarest label.")
