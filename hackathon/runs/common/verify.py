#!/usr/bin/env python3
"""Judge's verifier: recompute accuracy from every per-row results file in a run folder and
compare with the reported number; print the test-set hash and ledger total.
Usage: python3 verify.py runs/<task>"""
import csv, glob, hashlib, json, os, sys

run = sys.argv[1]
test = os.path.join(run, "data", "test.jsonl")
if os.path.exists(test):
    n = sum(1 for l in open(test) if l.strip())
    print(f"test set: {n} rows, sha256 {hashlib.sha256(open(test,'rb').read()).hexdigest()[:16]}")
led = os.path.join(run, "ledger.csv")
if os.path.exists(led):
    rows = list(csv.DictReader(open(led)))
    tot = 0.0
    for r in rows:
        for k in ("cost", "cost_usd", "usd"):
            if k in r and r[k]:
                tot += float(r[k]); break
    print(f"ledger: ${tot:.3f} over {len(rows)} calls")
mismatch = 0
for p in sorted(glob.glob(os.path.join(run, "results", "**", "*.json"), recursive=True)):
    try:
        d = json.load(open(p))
    except Exception:
        continue
    rows = d.get("rows") if isinstance(d, dict) else None
    if not rows or not isinstance(rows, list) or "correct" not in rows[0]:
        continue
    acc = sum(1 for r in rows if r.get("correct")) / len(rows)
    rep = d.get("accuracy")
    flag = ""
    if isinstance(rep, (int, float)) and abs(acc - rep) > 0.005:
        flag = "  <-- MISMATCH"; mismatch += 1
    print(f"{os.path.relpath(p, run):55s} n={len(rows):4d} recomputed={acc:.1%} reported={rep}{flag}")
print("verdict:", "all reported accuracies reproduce" if not mismatch else f"{mismatch} MISMATCHES")
