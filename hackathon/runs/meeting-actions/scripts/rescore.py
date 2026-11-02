#!/usr/bin/env python3
"""Scorer sensitivity: re-score cached outputs at other task-similarity thresholds (headline stays 0.6).
    python3 scripts/rescore.py results/*_v1_plain.json --sims 0.45 0.6 0.75
"""
import argparse, json, os, sys
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__))); sys.path.insert(0, ROOT)
import score as S
ap = argparse.ArgumentParser(); ap.add_argument("paths", nargs="+"); ap.add_argument("--sims", nargs="+", type=float, default=[0.45, 0.6, 0.75]); a = ap.parse_args()
print(f"{'run':44s} " + " ".join(f"F1@{s}" for s in a.sims))
for p in a.paths:
    d = json.load(open(p)); out = []
    for sim in a.sims:
        S.TOKEN_SIM = sim
        out.append(S.aggregate([S.score_rows(r["gold"], r["raw"]) for r in d["rows"]])["f1"])
    print(f"{d['model'].split('/')[-1] + ' + ' + d['prompt']:44s} " + " ".join(f"{x:6.3f}" for x in out))
