#!/usr/bin/env python3
"""Inject the results table, spend, leak check and few-shot variance into RESULTS.md (between markers)."""
import csv, glob, json, os, re, statistics, subprocess
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
table = subprocess.run(["python3", os.path.join(ROOT, "scripts", "results_table.py")], capture_output=True, text=True).stdout.strip()
rows = list(csv.DictReader(open(os.path.join(ROOT, "ledger.csv"))))
spend = sum(float(r["cost"]) for r in rows); gen = sum(float(r["cost"]) for r in rows if r["tag"] == "gen")
leak = open(os.path.join(ROOT, "results", "leak_check.txt")).read().strip()
fs = [json.load(open(p))["f1"] for p in sorted(glob.glob(os.path.join(ROOT, "results", "glm-5p3-flash_v4_fewshot*.json")))]
v1 = [json.load(open(p))["f1"] for p in sorted(glob.glob(os.path.join(ROOT, "results", "glm-5p3-flash_v1_plain*.json")))]
var = (f"glm-5p3-flash plain: {statistics.mean(v1):.3f} ± {(max(v1)-min(v1))/2:.3f} over {len(v1)} runs ({', '.join(f'{x:.3f}' for x in v1)}); "
       f"glm-5p3-flash rubric + 5-shot: {statistics.mean(fs):.3f} ± {(max(fs)-min(fs))/2:.3f} over {len(fs)} runs ({', '.join(f'{x:.3f}' for x in fs)}).")
s = open(os.path.join(ROOT, "RESULTS.md")).read()
s = re.sub(r"<!-- TABLE -->.*?<!-- /TABLE -->", "<!-- TABLE -->\n" + table + "\n<!-- /TABLE -->", s, flags=re.S)
s = re.sub(r"<!-- VARIANCE -->.*?<!-- /VARIANCE -->", "<!-- VARIANCE -->" + var + "<!-- /VARIANCE -->", s, flags=re.S)
s = re.sub(r"Spend: .*", f"Spend: ${spend:.2f} inference (${gen:.2f} of it data generation; ledger.csv, {len(rows)} calls), $0.00 training", s)
s = re.sub(r"Leak check:\n```.*?```", "Leak check:\n```\n" + leak + "\n```", s, flags=re.S)
open(os.path.join(ROOT, "RESULTS.md"), "w").write(s); print(f"RESULTS.md updated; spend ${spend:.3f}; {var}")
