#!/usr/bin/env python3
"""Saves demo/empty_response.json: one raw Fireworks API response where the model spent its whole max_tokens budget on
hidden reasoning and returned empty content, together with the exact request body that caused it.
Picks the first row with finish_reason "length" from sweep/results/<model>__v1_plain+mt512__s0.json and re-sends it (temperature 0).
Usage: python3 make_empty_response.py [model] [max_tokens] [source_tag]
  e.g. python3 make_empty_response.py glm-5p3-flash 20 v1_plain+mt512  (rows that hit the cap at 512, re-sent with a 20-token cap)"""
import os, sys, json, datetime
HERE = os.path.dirname(os.path.abspath(__file__)); SUB = os.path.dirname(HERE); sys.path.insert(0, SUB)
import fw
fw.LEDGER = os.path.join(SUB, "sweep", "ledger.csv"); fw.CAP = 5.00
from run_eval import build_system
model = sys.argv[1] if len(sys.argv) > 1 else "nemotron-lightning-3p5-30b-a3b"; mt = int(sys.argv[2]) if len(sys.argv) > 2 else 512
src = sys.argv[3] if len(sys.argv) > 3 else f"v1_plain+mt{mt}"
res = json.load(open(os.path.join(SUB, "sweep", "results", f"{model}__{src}__s0.json")))
capped = [r for r in res["rows"] if r["finish_reason"] == "length" and not r["raw"].strip()]
print(f"{len(capped)} of {res['n']} rows hit the cap with empty content in {src}")
row = capped[0]
catalog = json.load(open(os.path.join(SUB, "data", "catalog.json"))); template = open(os.path.join(SUB, "prompts", "v1_plain.txt")).read()
msgs = [{"role": "system", "content": build_system(template, catalog, [])}, {"role": "user", "content": row["text"]}]
request = {"model": fw.model_id(model), "max_tokens": mt, "temperature": 0, "messages": msgs}
r = fw.chat(model, msgs, max_tokens=mt, note="demo_empty_response")
out = {"what": "Raw API response where the model returned empty content because the max_tokens budget was consumed by hidden reasoning (finish_reason = length).",
       "captured": datetime.datetime.now().isoformat(timespec="seconds"), "endpoint": fw.URL, "test_row_id": row["id"], "gold_tool": row["label"],
       "request": request, "response": r["raw"],
       "observed": {"content": r["content"], "finish_reason": r["finish_reason"], "completion_tokens": r["out_tokens"], "reasoning_tokens": r["reasoning_tokens"],
                    "reasoning_excerpt": (r["reasoning"] or "")[:600], "latency_s": round(r["latency"], 3), "scored_as": "invalid (no catalog name in content)"},
       "rows_capped_in_full_run": len(capped), "source_results_file": f"submission/sweep/results/{model}__{src}__s0.json"}
json.dump(out, open(os.path.join(HERE, "empty_response.json"), "w"), indent=1)
print("content repr:", repr(r["content"]), "| finish:", r["finish_reason"], "| completion tokens:", r["out_tokens"], "| reasoning tokens:", r["reasoning_tokens"])
print("saved", os.path.join(HERE, "empty_response.json"))
