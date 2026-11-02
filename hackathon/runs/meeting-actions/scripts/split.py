#!/usr/bin/env python3
"""Rebuild data/train.jsonl = all rows not in the locked test set. Never touches data/test.jsonl."""
import json, os
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
test_ids = set(json.load(open(os.path.join(ROOT, "data", "test_ids.json"))))
rows = [json.loads(l) for l in open(os.path.join(ROOT, "data", "all.jsonl")) if l.strip()]
train = sorted((r for r in rows if r["id"] not in test_ids), key=lambda r: r["id"])
with open(os.path.join(ROOT, "data", "train.jsonl"), "w") as f:
    for r in train: f.write(json.dumps(r) + "\n")
print(f"train.jsonl: {len(train)} rows ({len(rows)} total, {len(test_ids)} test)")
