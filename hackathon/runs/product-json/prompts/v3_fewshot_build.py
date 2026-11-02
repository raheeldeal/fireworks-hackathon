#!/usr/bin/env python3
"""Build prompts/v3_fewshot.txt = v2 rubric + 5 worked examples drawn from data/train.jsonl (never from test)."""
import json, os, random
HERE = os.path.dirname(os.path.abspath(__file__))
rows = [json.loads(l) for l in open(os.path.join(HERE, "..", "data", "train.jsonl"))]
rng = random.Random(11)
# pick examples that exercise the hard rules: was-price, alt colours, multipack, bundle, null fields
def pick(pred):
    c = [r for r in rows if pred(r)]; return rng.choice(c) if c else rng.choice(rows)
ex = [pick(lambda r: r["noise"]["was_price"]), pick(lambda r: r["noise"]["alt_colors"]), pick(lambda r: r["gold"]["quantity"] > 1 and not r["gold"]["is_bundle"]),
      pick(lambda r: r["gold"]["is_bundle"]), pick(lambda r: r["gold"]["price_usd"] is None or r["gold"]["material"] is None)]
base = open(os.path.join(HERE, "v2_rubric.txt")).read()
shots = "\n\nExamples:\n" + "\n\n".join(f"Listing:\n{r['text']}\nJSON:\n{json.dumps(r['gold'])}" for r in ex)
open(os.path.join(HERE, "v3_fewshot.txt"), "w").write(base + shots + "\n")
print("wrote v3_fewshot.txt with ids", [r["id"] for r in ex])
