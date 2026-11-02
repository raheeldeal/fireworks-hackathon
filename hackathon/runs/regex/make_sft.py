#!/usr/bin/env python3
"""Format data/train.jsonl into Fireworks `messages` JSONL for LoRA SFT, and estimate tokens.

    venv/bin/python make_sft.py            -> data/sft_train.jsonl (+ token estimate on stdout)
    venv/bin/python make_sft.py --few-shot -> data/fewshot5.jsonl (5 fixed train rows for the 5-shot prompt)

The system prompt is prompts/v1_plain.txt so the tuned model is scored with the same prompt as the baseline.
"""
import argparse
import json
import os
import random

HERE = os.path.dirname(os.path.abspath(__file__))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--few-shot", action="store_true")
    ap.add_argument("--max-rows", type=int, default=0)
    args = ap.parse_args()
    rows = [json.loads(l) for l in open(os.path.join(HERE, "data", "train.jsonl")) if l.strip()]
    system = open(os.path.join(HERE, "prompts", "v1_plain.txt")).read().strip()
    if args.few_shot:
        rng = random.Random(5)
        kb = [r for r in rows if r["source"] == "KB13"]
        picks = rng.sample(kb, 5)
        with open(os.path.join(HERE, "data", "fewshot5.jsonl"), "w") as f:
            for r in picks:
                f.write(json.dumps({"id": r["id"], "text": r["text"], "gold": r["gold"]}) + "\n")
        print("wrote data/fewshot5.jsonl:", [r["id"] for r in picks])
        return
    if args.max_rows:
        rows = rows[: args.max_rows]
    out = os.path.join(HERE, "data", "sft_train.jsonl")
    chars = 0
    with open(out, "w") as f:
        for r in rows:
            msgs = [{"role": "system", "content": system}, {"role": "user", "content": r["text"]}, {"role": "assistant", "content": r["gold"]}]
            f.write(json.dumps({"messages": msgs}, ensure_ascii=False) + "\n")
            chars += sum(len(m["content"]) for m in msgs)
    est = chars / 3.5  # conservative chars-per-token for regex-heavy text
    print(f"wrote {out}: {len(rows)} rows, ~{chars} chars, ~{est:,.0f} tokens per epoch (estimate, 3.5 chars/token)")


if __name__ == "__main__":
    main()
