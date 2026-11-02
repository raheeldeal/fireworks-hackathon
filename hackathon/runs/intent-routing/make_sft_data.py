#!/usr/bin/env python3
"""Format data/train.jsonl into Fireworks chat-messages JSONL for SFT (data/sft_train.jsonl).
Short system prompt on purpose: the tuned model learns the label set, so scoring via the serverless sampler
costs ~40 prefill tokens per row instead of ~1,600. Run check_leak.py on the output before any training."""
import json, os
HERE = os.path.dirname(os.path.abspath(__file__))
SYS = "Classify the customer's banking support message into exactly one Banking77 intent label. Reply with only the label."
rows = [json.loads(l) for l in open(os.path.join(HERE, "data", "train.jsonl"))]
out = os.path.join(HERE, "data", "sft_train.jsonl")
with open(out, "w") as f:
    for r in rows:
        f.write(json.dumps({"messages": [{"role": "system", "content": SYS},
                                         {"role": "user", "content": r["text"]},
                                         {"role": "assistant", "content": r["label"]}]}) + "\n")
tok = sum(len(SYS) // 4 + len(r["text"]) // 4 + len(r["label"]) // 4 + 12 for r in rows)
print(f"wrote {out}: {len(rows)} rows, ~{tok} training tokens (well under the 300k rule)")
open(os.path.join(HERE, "prompts", "v0_sft_short.txt"), "w").write(SYS)
