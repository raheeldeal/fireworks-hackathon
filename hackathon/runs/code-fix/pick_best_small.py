#!/usr/bin/env python3
"""Print the model id of the best small model from the plain baseline results (ties -> cheaper)."""
import glob, json, os
HERE = os.path.dirname(os.path.abspath(__file__))
from run_eval import PRICING
SMALL = ["nemotron-lightning-3p5-30b-a3b", "glm-5p3-flash", "gpt-oss-120b", "deepseek-v4p1-flash"]
best = None
for m in SMALL:
    p = os.path.join(HERE, "results", f"{m}_v1_plain.json")
    if os.path.exists(p):
        r = json.load(open(p))
        key = (r["accuracy"], -r["cost_per_1k_requests_usd"])
        if best is None or key > best[0]:
            best = (key, r["model"])
print(best[1] if best else "")
