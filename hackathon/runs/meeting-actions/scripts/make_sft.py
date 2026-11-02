#!/usr/bin/env python3
"""Format data/train.jsonl into Fireworks chat JSONL for SFT: system = v2 rubric, user = transcript, assistant = gold JSON.
    python3 scripts/make_sft.py  -> data/sft_train.jsonl ; then python3 ../common/check_leak.py data/test.jsonl data/sft_train.jsonl
"""
import json, os
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sysmsg = open(os.path.join(ROOT, "prompts", "v2_rubric.txt")).read().strip()
test_ids = set(json.load(open(os.path.join(ROOT, "data", "test_ids.json"))))
n, toks = 0, 0
with open(os.path.join(ROOT, "data", "sft_train.jsonl"), "w") as out:
    for l in open(os.path.join(ROOT, "data", "train.jsonl")):
        r = json.loads(l)
        assert r["id"] not in test_ids
        row = {"messages": [{"role": "system", "content": sysmsg}, {"role": "user", "content": "Transcript:\n\n" + r["text"]},
                            {"role": "assistant", "content": json.dumps(r["items"])}]}
        out.write(json.dumps(row) + "\n"); n += 1
        toks += sum(len(m["content"]) for m in row["messages"]) // 4
print(f"wrote data/sft_train.jsonl: {n} rows, ~{toks:,} tokens (chars/4)")
