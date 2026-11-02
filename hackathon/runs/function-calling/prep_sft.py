#!/usr/bin/env python3
"""Format data/train.jsonl into Fireworks chat JSONL for SFT (plain-prompt JSON variant: tools in the system
prompt, assistant replies with the call JSON). Writes data/sft_train.jsonl and prints a token estimate."""
import json, os, sys
HERE = os.path.dirname(os.path.abspath(__file__))
SYSTEM = open(os.path.join(HERE, "prompts", "v1_plain.txt")).read().strip()
MAX_TOKENS = 300_000          # PROTOCOL rule 4
rows = [json.loads(l) for l in open(os.path.join(HERE, "data", "train.jsonl"))]
out, est = [], 0
for r in rows:
    tools_text = json.dumps([t["function"] for t in r["tools"]], ensure_ascii=False)
    msgs = [{"role": "system", "content": SYSTEM + "\n\nAvailable tools (JSON):\n" + tools_text}]
    for m in r["messages"]:
        msgs.append({"role": m["role"], "content": m["content"]})
    msgs.append({"role": "assistant", "content": json.dumps(r["answer"], ensure_ascii=False)})
    toks = sum(len(m["content"]) for m in msgs) / 3.5 + 20     # rough: 3.5 chars/token
    if est + toks > MAX_TOKENS:
        break
    est += toks
    out.append({"messages": msgs})
with open(os.path.join(HERE, "data", "sft_train.jsonl"), "w") as f:
    for o in out: f.write(json.dumps(o, ensure_ascii=False) + "\n")
print(f"wrote {len(out)}/{len(rows)} rows, ~{est:,.0f} estimated tokens (cap {MAX_TOKENS:,})")
