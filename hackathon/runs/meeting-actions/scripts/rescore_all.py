#!/usr/bin/env python3
"""Recompute every row's score from its cached raw output with the current score.py, rewrite summaries.
Used after a scorer change so all cached runs stay comparable (no API calls)."""
import glob, json, os, statistics, sys
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__))); sys.path.insert(0, ROOT)
import score as S
for p in sorted(glob.glob(os.path.join(ROOT, "results", "*.json"))):
    d = json.load(open(p))
    if "rows" not in d or d["model"].startswith(("route(", "filter(")): continue
    for r in d["rows"]:
        r["score"] = S.score_rows(r["gold"], r["raw"]); sc = r["score"]
        r["correct"] = sc["valid"] and sc["tp"] == sc["n_gold"] == sc["n_pred"] and sc["due_correct"] == sc["due_total"]
    agg = S.aggregate([r["score"] for r in d["rows"]])
    d.update({"accuracy": agg["f1"], "precision": agg["precision"], "recall": agg["recall"], "f1": agg["f1"], "due_acc": agg["due_acc"], "exact_row_acc": agg["exact_row_acc"], "invalid_outputs": agg["invalid"]})
    json.dump(d, open(p, "w"), indent=1); print(f"{os.path.basename(p):50s} F1 {agg['f1']:.3f} due {agg['due_acc']:.3f}")
