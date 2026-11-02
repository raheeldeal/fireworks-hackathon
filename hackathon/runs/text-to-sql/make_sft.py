"""Format data/train.jsonl into Fireworks messages JSONL for LoRA SFT. Uses the plain prompt so the tuned model is scored with v1_plain."""
import json, sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from run_eval import user_message
from schema_util import approx_tokens
sysp = open("prompts/v1_plain.txt").read().strip()
rows = [json.loads(l) for l in open("data/train.jsonl")]
tok = 0
with open("data/sft_train.jsonl", "w") as f:
    for r in rows:
        msgs = [{"role": "system", "content": sysp}, {"role": "user", "content": user_message(r)}, {"role": "assistant", "content": r["gold_sql"]}]
        tok += sum(approx_tokens(m["content"]) for m in msgs)
        f.write(json.dumps({"messages": msgs}) + "\n")
print(f"{len(rows)} examples, ~{tok} tokens")
