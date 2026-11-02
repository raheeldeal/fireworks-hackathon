#!/usr/bin/env python3
"""raw/gen_raw.jsonl -> data/test.jsonl (first 200 verified rows, shuffled with fixed seed; LOCKED) and data/train.jsonl (the rest)."""
import json, random, os, sys
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE); import gen_data
rows = [json.loads(l) for l in open(os.path.join(HERE, "raw", "gen_raw.jsonl")) if l.strip()]
for r in rows: r["verify"] = gen_data.verify(r["text"], r["gold"])  # re-verify with the final rules
good = [r for r in rows if not r["verify"]]
seen, uniq = set(), []
for r in good:
    k = r["text"].strip().lower()
    if k not in seen: seen.add(k); uniq.append(r)
random.Random(42).shuffle(uniq)
n_test = int(sys.argv[1]) if len(sys.argv) > 1 else 200
test, train = uniq[:n_test], uniq[n_test:]
tp = os.path.join(HERE, "data", "test.jsonl")
if os.path.exists(tp) and os.path.getsize(tp) > 0:
    sys.exit("data/test.jsonl already exists and is locked; refusing to overwrite")
with open(tp, "w") as f:
    for r in test: f.write(json.dumps({"id": r["id"], "text": r["text"], "gold": r["gold"], "noise": r["noise"]}) + "\n")
with open(os.path.join(HERE, "data", "train.jsonl"), "w") as f:
    for r in train: f.write(json.dumps({"id": r["id"], "text": r["text"], "gold": r["gold"], "noise": r["noise"]}) + "\n")
print(f"{len(rows)} raw, {len(good)} verified, {len(uniq)} unique -> test {len(test)}, train {len(train)}")
