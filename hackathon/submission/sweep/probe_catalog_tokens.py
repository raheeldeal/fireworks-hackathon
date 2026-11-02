#!/usr/bin/env python3
"""Measure catalog tokens per model: prompt_tokens(template with catalog) - prompt_tokens(template without catalog), same user text.
Two max_tokens=1 calls per model. Writes sweep/catalog_tokens.json."""
import os, sys, json
HERE = os.path.dirname(os.path.abspath(__file__)); SUB = os.path.dirname(HERE); sys.path.insert(0, SUB)
import fw
fw.LEDGER = os.path.join(HERE, "ledger.csv"); fw.CAP = 5.00
from run_eval import catalog_text
catalog = json.load(open(os.path.join(SUB, "data", "catalog.json")))
template = open(os.path.join(SUB, "prompts", "v1_plain.txt")).read()
user = "placeholder request"
out = json.load(open(os.path.join(HERE, "catalog_tokens.json"))) if os.path.exists(os.path.join(HERE, "catalog_tokens.json")) else {}
for m in fw.PRICING:
    short = m.split("/")[-1]
    if short in out: continue
    extra = None  # max_tokens=1; only prompt_tokens matters
    full = fw.chat(m, [{"role": "system", "content": template.replace("{CATALOG}", catalog_text(catalog))}, {"role": "user", "content": user}], max_tokens=1, extra=extra, note="probe_catalog")
    bare = fw.chat(m, [{"role": "system", "content": template.replace("{CATALOG}", "")}, {"role": "user", "content": user}], max_tokens=1, extra=extra, note="probe_catalog")
    out[short] = {"prompt_tokens_with_catalog": full["in_tokens"], "prompt_tokens_without_catalog": bare["in_tokens"], "catalog_tokens": full["in_tokens"] - bare["in_tokens"]}
    print(short, out[short])
json.dump(out, open(os.path.join(HERE, "catalog_tokens.json"), "w"), indent=1)
