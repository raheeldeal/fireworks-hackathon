#!/usr/bin/env python3
"""Build prompts/v4_fewshot.txt from 5 train rows (never test rows): rubric + 5 worked examples."""
import json, os, random
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
train = [json.loads(l) for l in open(os.path.join(ROOT, "data", "train.jsonl")) if l.strip()]
test_ids = set(json.load(open(os.path.join(ROOT, "data", "test_ids.json"))))
train = [r for r in train if r["id"] not in test_ids]
rng = random.Random(11); shots = rng.sample(train, 5)
rubric = open(os.path.join(ROOT, "prompts", "v2_rubric.txt")).read().strip()
parts = [rubric, "\nHere are five worked examples. Study how discussed-but-unassigned topics are excluded.\n"]
for i, r in enumerate(shots, 1):
    parts.append(f"### Example {i}\nTranscript:\n{r['text'].strip()}\n\nOutput:\n{json.dumps(r['items'])}\n")
parts.append("Now extract the action items from the transcript the user provides. Output only the JSON array.")
open(os.path.join(ROOT, "prompts", "v4_fewshot.txt"), "w").write("\n".join(parts))
print("wrote prompts/v4_fewshot.txt with shots", [s["id"] for s in shots])
