#!/usr/bin/env python3
"""Build locked, stratified test.jsonl (2 per intent = 154 rows) from the official Banking77 TEST split,
and train.jsonl (4 per intent = 308 rows) from the official TRAIN split. Deterministic (seed 20261101).
Source: PolyAI-LDN/task-specific-datasets banking_data (CC-BY-4.0), same data as HF PolyAI/banking77."""
import csv, json, random, collections, sys
SEED = 20261101
TEST_PER = 2
TRAIN_PER = 4

def read(p):
    with open(p, newline="") as f:
        return [(r["text"].strip(), r["category"].strip()) for r in csv.DictReader(f)]

def stratified(rows, per, rng):
    by = collections.defaultdict(list)
    for t, c in rows:
        by[c].append(t)
    out = []
    for c in sorted(by):
        texts = sorted(set(by[c]))
        rng.shuffle(texts)
        out += [(t, c) for t in texts[:per]]
    return out

rng = random.Random(SEED)
test = stratified(read("raw_download/test.csv"), TEST_PER, rng)
train_pool = read("raw_download/train.csv")
test_texts = {t.lower() for t, _ in test}
train_pool = [(t, c) for t, c in train_pool if t.lower() not in test_texts]
train = stratified(train_pool, TRAIN_PER, rng)
rng.shuffle(test)  # mix intents so order carries no signal
with open("data/test.jsonl", "w") as f:
    for i, (t, c) in enumerate(test, 1):
        f.write(json.dumps({"id": i, "text": t, "label": c}) + "\n")
with open("data/train.jsonl", "w") as f:
    for i, (t, c) in enumerate(train, 1):
        f.write(json.dumps({"id": i, "text": t, "label": c}) + "\n")
print(f"test {len(test)} rows ({len(set(c for _,c in test))} intents), train {len(train)} rows")
