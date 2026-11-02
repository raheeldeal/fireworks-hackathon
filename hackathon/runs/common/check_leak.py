#!/usr/bin/env python3
"""Fail if any training example's input text appears in the locked test set.
Usage: python3 check_leak.py test.jsonl train.jsonl [more_train.jsonl ...]
Each line is JSON; the input text is taken from the first present field among: text, input, question, prompt,
or the last user message in a `messages` list."""
import hashlib, json, sys

def key(row):
    for f in ("text", "input", "question", "prompt"):
        if f in row:
            return str(row[f]).strip().lower()
    if "messages" in row:
        users = [m for m in row["messages"] if m.get("role") == "user"]
        if users:
            c = users[-1].get("content")
            return (c if isinstance(c, str) else json.dumps(c)).strip().lower()
    return json.dumps(row, sort_keys=True).lower()

def load(p):
    return [json.loads(l) for l in open(p) if l.strip()]

test = load(sys.argv[1])
test_keys = {key(r) for r in test}
digest = hashlib.sha256(open(sys.argv[1], "rb").read()).hexdigest()[:16]
print(f"test set: {len(test)} rows, sha256 {digest}")
bad = 0
for p in sys.argv[2:]:
    rows = load(p)
    hits = [r for r in rows if key(r) in test_keys]
    print(f"{p}: {len(rows)} rows, {len(hits)} overlap with test")
    bad += len(hits)
sys.exit(1 if bad else 0)
