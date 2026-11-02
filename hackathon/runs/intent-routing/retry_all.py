#!/usr/bin/env python3
"""Re-run only the errored (429/5xx) rows of every results/*.json, sequentially with low concurrency. Idempotent."""
import glob, json, os, subprocess, sys
HERE = os.path.dirname(os.path.abspath(__file__))
for p in sorted(glob.glob(os.path.join(HERE, "results", "*.json"))):
    d = json.load(open(p))
    if "rows" not in d or not any(r.get("error") for r in d["rows"]):
        continue
    name = d["prompt"]
    effort = d.get("effort")
    json_mode = d.get("json_mode")
    base = name
    if effort and base.endswith("_" + effort):
        base = base[: -len(effort) - 1]
    if base.endswith("_json"):
        base = base[:-5]
    cmd = [sys.executable, os.path.join(HERE, "run_eval.py"), "--model", d["model"], "--prompt", os.path.join(HERE, "prompts", base + ".txt"),
           "--workers", "2", "--retry-errors", p]
    if effort: cmd += ["--effort", effort]
    if json_mode: cmd += ["--json-mode"]
    if d.get("seed"): cmd += ["--seed", str(d["seed"])]
    if d["n"] < 154: cmd += ["--limit", str(d["n"])]
    n_err = sum(1 for r in d["rows"] if r.get("error"))
    print(f"== retry {n_err} rows: {os.path.basename(p)}", flush=True)
    subprocess.run(cmd, check=False)
