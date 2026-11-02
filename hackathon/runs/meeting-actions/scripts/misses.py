#!/usr/bin/env python3
"""Show the misses of a results file: false positives (extra predicted items), false negatives (gold items not found),
and due-date mismatches, each tagged with the distractor kind when the FP matches a distractor.
    python3 scripts/misses.py results/<file>.json [--n 20]
"""
import argparse, json, os, sys
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__))); sys.path.insert(0, ROOT)
import score as S
ap = argparse.ArgumentParser(); ap.add_argument("path"); ap.add_argument("--n", type=int, default=25); a = ap.parse_args()
d = json.load(open(a.path))
test = {json.loads(l)["id"]: json.loads(l) for l in open(os.path.join(ROOT, "data", "test.jsonl"))}
fp, fn, due, kinds = [], [], [], {}
for r in d["rows"]:
    sc, pred, gold, ex = r["score"], r["pred"] or [], r["gold"], test[r["id"]]
    for j in sc["unmatched_pred"]:
        p = pred[j]; kind = "other"
        for dis in ex["distractors"]:
            if S.token_set_ratio(p.get("task", ""), dis["text"]) >= 0.5:
                kind = "distractor:" + dis["kind"]; break
        else:
            for i in sc["unmatched_gold"]:
                g = gold[i]
                if S.token_set_ratio(p.get("task", ""), g["task"]) >= 0.6: kind = "owner-mismatch"
                elif S.norm_owner(p.get("owner")) == S.norm_owner(g["owner"]): kind = "task-paraphrase<0.6"
        kinds[kind] = kinds.get(kind, 0) + 1
        fp.append((r["id"], kind, p))
    for i in sc["unmatched_gold"]:
        fn.append((r["id"], gold[i]))
    for m in sc["matches"]:
        if not m["due_ok"]:
            due.append((r["id"], gold[m["gold"]]["due"], pred[m["pred"]].get("due")))
print(f"{d['model'].split('/')[-1]} + {d['prompt']}: F1 {d['f1']:.3f}  FP {len(fp)}  FN {len(fn)}  due-wrong {len(due)}  invalid {d['invalid_outputs']}")
print("FP kinds:", json.dumps(kinds))
print("\n-- false positives --")
for x in fp[: a.n]: print(x[0], x[1], json.dumps(x[2]))
print("\n-- false negatives (gold not found) --")
for x in fn[: a.n]: print(x[0], json.dumps(x[1]))
print("\n-- due mismatches (gold vs pred) --")
for x in due[: a.n]: print(x)
