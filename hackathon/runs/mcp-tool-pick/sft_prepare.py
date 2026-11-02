#!/usr/bin/env python3
"""Format data/train.jsonl into Fireworks chat JSONL for catalog-free SFT: user text -> tool name. Writes data/train_sft.jsonl."""
import json
SYS = "You are a tool router for an agent platform with 100 tools. Reply with only the exact tool name (server.action) that best handles the user's request."
rows = [json.loads(l) for l in open("data/train.jsonl")]
with open("data/train_sft.jsonl", "w") as f:
    for r in rows:
        f.write(json.dumps({"messages": [{"role": "system", "content": SYS}, {"role": "user", "content": r["text"]}, {"role": "assistant", "content": r["label"]}]}) + "\n")
chars = sum(len(json.dumps(json.loads(l))) for l in open("data/train_sft.jsonl"))
print(f"wrote {len(rows)} rows, ~{chars//4} tokens (chars/4)")
