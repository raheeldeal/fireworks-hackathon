"""Re-score configs on the validated test subset (data/test_audit.jsonl).

  python validate_eval.py results/r5_full.json results/r17_kimi.json:repair results/r6_ft1.json

test_audit.jsonl labels the test questions no config answered (plus t182) after reviewing gold rows against model
rows: gold_wrong (gold does not answer the question), ambiguous (several correct answers), format_only (gold is right,
models return the same entities in another shape). Review by Claude Code, not by humans.

  all        every question, strict (the headline elsewhere)
  valid      drops gold_wrong and ambiguous: questions with one fair answer
  valid-L    valid, also without the gold queries that use LIMIT without ORDER BY (an arbitrary subset)
Each config after the first is compared with the first on `valid`, paired (compare.py).
"""
import json, re, sys

import metrics
from compare import compare
from score import has_order_by

audit = {r["id"]: r["label"] for r in (json.loads(l) for l in open("data/test_audit.jsonl"))}
test = [json.loads(l) for l in open("data/test.jsonl")]
valid = {t["id"] for t in test if audit.get(t["id"]) not in ("gold_wrong", "ambiguous")}
limit_only = {t["id"] for t in test if re.search(r"\blimit\b", t["cypher"], re.I) and not has_order_by(t["cypher"])}
subsets = {"all": {t["id"] for t in test}, "valid": valid, "valid-L": valid - limit_only}
print("subset sizes:", {k: len(v) for k, v in subsets.items()})

scored = {}
for spec in sys.argv[1:]:
    path, _, stage = spec.partition(":")
    doc = json.load(open(path))
    stage = stage or list(doc["views"])[-1]
    ok = {r["id"]: metrics.cut(r, stage)["outcome"] == "correct" for r in doc["rows"]}
    name = f"{doc['tag']}:{stage}"
    scored[name] = ok
    cells = []
    for sname, ids in subsets.items():
        k = sum(ok[i] for i in ids)
        lo, hi = metrics.wilson(k, len(ids))
        cells.append(f"{sname} {k / len(ids):.1%} [{lo:.1%}-{hi:.1%}]")
    print(f"{name:<26} " + "   ".join(cells))
first = list(scored)[0]
for name in list(scored)[1:]:
    r = compare({i: scored[first][i] for i in valid}, {i: scored[name][i] for i in valid})
    print(f"valid subset: {name} - {first} = {r['diff']:+.1%}  CI [{r['ci95'][0]:+.1%}, {r['ci95'][1]:+.1%}]  p={r['p_mcnemar']:.4f}")
