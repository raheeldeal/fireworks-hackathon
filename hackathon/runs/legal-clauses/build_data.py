#!/usr/bin/env python3
"""Build the locked test set and the training set from LEDGAR (lex_glue/ledgar).
Stratified: 2 test rows per class (200 total) from the official test split, 5 train rows per class (500) from the
official train split. Clauses are kept under ~400 tokens using a word-count proxy (<= 250 words; legal text runs
~1.4 tokens/word). Deterministic (seed 20261101). Run once; test.jsonl is then locked.
"""
import json, random, hashlib, collections, sys
LABELS = json.load(open("data/labels.json"))["labels"]
NAMES = [l["name"] for l in LABELS]
MAX_WORDS = 250
SEED = 20261101

def load(p):
    return [json.loads(l) for l in open(p) if l.strip()]

def ok(r):
    w = len(r["text"].split())
    return 20 <= w <= MAX_WORDS

def stratified(rows, per_class, rng, exclude_texts=set()):
    by = collections.defaultdict(list)
    for r in rows:
        if ok(r) and r["text"].strip().lower() not in exclude_texts:
            by[r["label"]].append(r)
    out = []
    for lab in range(len(NAMES)):
        pool = by[lab]
        rng.shuffle(pool)
        if len(pool) < per_class:
            print(f"WARNING: class {lab} {NAMES[lab]} has only {len(pool)} eligible rows", file=sys.stderr)
        out.extend(pool[:per_class])
    return out

def write(rows, path, prefix):
    with open(path, "w") as f:
        for i, r in enumerate(rows):
            f.write(json.dumps({"id": f"{prefix}{i:03d}", "text": r["text"].strip(), "label": NAMES[r["label"]]}) + "\n")

if __name__ == "__main__":
    rng = random.Random(SEED)
    test = stratified(load("data/raw/ledgar_test.jsonl"), 2, rng)
    # classes with fewer than 2 eligible rows in the test split are topped up from the (also held-out) validation split
    have = collections.Counter(r["label"] for r in test)
    val = load("data/raw/ledgar_validation.jsonl")
    for lab in range(len(NAMES)):
        if have[lab] < 2:
            pool = [r for r in val if r["label"] == lab and ok(r)]
            rng.shuffle(pool)
            test.extend(pool[: 2 - have[lab]])
            print(f"topped up class {NAMES[lab]} from validation with {2 - have[lab]} rows", file=sys.stderr)
    rng.shuffle(test)
    write(test, "data/test.jsonl", "t")
    test_texts = {r["text"].strip().lower() for r in test}
    train = stratified(load("data/raw/ledgar_train.jsonl"), 5, rng, test_texts)
    rng.shuffle(train)
    write(train, "data/train.jsonl", "r")
    print("test", len(test), "train", len(train))
    print("test sha256", hashlib.sha256(open("data/test.jsonl", "rb").read()).hexdigest())
