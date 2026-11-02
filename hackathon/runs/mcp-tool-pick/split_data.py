#!/usr/bin/env python3
"""Stratified split of data/all.jsonl into data/test.jsonl (180) and data/train.jsonl (320). Seeded; run once."""
import json, random, collections, os, sys
if os.path.exists("data/test.jsonl"):
    sys.exit("data/test.jsonl exists; refusing to overwrite the locked test set")
rows = [json.loads(l) for l in open("data/all.jsonl")]
by_tool = collections.defaultdict(list)
for r in rows: by_tool[r["tool"]].append(r)
rng = random.Random(2026)
tools = sorted(by_tool); rng.shuffle(tools)
test, train = [], []
for i, t in enumerate(tools):
    items = by_tool[t][:]; rng.shuffle(items)
    k = 2 if i < 80 else 1          # 80*2 + 20*1 = 180
    test += items[:k]; train += items[k:]
rng.shuffle(test); rng.shuffle(train)
for name, rs in (("test", test), ("train", train)):
    with open(f"data/{name}.jsonl", "w") as f:
        for r in rs: f.write(json.dumps({"id": r["id"], "text": r["text"], "label": r["tool"], "style": r["style"]}) + "\n")
print(len(test), len(train))
