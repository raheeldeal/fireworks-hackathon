"""Does a score come from near-duplicate questions? Re-score configs on test questions with no close train paraphrase.

  python contamination.py --train data/sft_ft1_gold.jsonl data/train.jsonl -- results/r5_full.json results/r6_ft1.json

The dataset has paraphrased duplicates across its train and test splits (e.g. p01475). For every test question we take
the highest word-overlap (Jaccard, same words as retrieve.py) with any question in the given training files, same graph.
A test question is "clean" when that overlap is below --threshold. Each config is then scored on the clean subset only.
"""
import argparse, json, sys
from collections import defaultdict

import metrics
from compare import compare
from retrieve import words


def jaccard(a, b):
    return len(a & b) / len(a | b) if a | b else 0.0


def main():
    argv = sys.argv[1:]
    split = argv.index("--") if "--" in argv else len(argv)
    ap = argparse.ArgumentParser()
    ap.add_argument("--train", nargs="+", required=True, help="every file whose questions a config saw in training or prompts")
    ap.add_argument("--test", default="data/test.jsonl")
    ap.add_argument("--threshold", type=float, default=0.6)
    args = ap.parse_args(argv[:split])
    result_specs = argv[split + 1:]

    seen = defaultdict(list)
    for path in args.train:
        for line in open(path):
            r = json.loads(line)
            seen[r["graph"]].append(words(r["question"]))
    test = [json.loads(l) for l in open(args.test)]
    closest = {t["id"]: max((jaccard(words(t["question"]), w) for w in seen[t["graph"]]), default=0.0) for t in test}
    clean = {i for i, s in closest.items() if s < args.threshold}
    for cut in (0.9, 0.8, 0.6, 0.4):
        print(f"test questions with a train paraphrase at overlap >= {cut}: {sum(s >= cut for s in closest.values())}")
    print(f"clean subset (overlap < {args.threshold}): {len(clean)} of {len(test)}\n")

    scored = {}
    for spec in result_specs:
        path, _, stage = spec.partition(":")
        doc = json.load(open(path))
        stage = stage or list(doc["views"])[-1]
        ok = {r["id"]: metrics.cut(r, stage)["outcome"] == "correct" for r in doc["rows"]}
        name = f"{doc['tag']}:{stage}"
        scored[name] = ok
        acc_all = sum(ok.values()) / len(ok)
        acc_clean = sum(ok[i] for i in clean) / len(clean)
        acc_dup = sum(ok[i] for i in ok if i not in clean) / max(1, len(ok) - len(clean))
        print(f"{name:<28} all {acc_all:.1%}   clean {acc_clean:.1%} (n={len(clean)})   near-dup {acc_dup:.1%} (n={len(ok) - len(clean)})")
    names = list(scored)
    for b in names[1:]:  # each later config vs the first, on the clean subset only
        r = compare({i: scored[names[0]][i] for i in clean}, {i: scored[b][i] for i in clean})
        print(f"clean subset: {b} - {names[0]} = {r['diff']:+.1%}  CI [{r['ci95'][0]:+.1%}, {r['ci95'][1]:+.1%}]  p={r['p_mcnemar']:.4f}")


if __name__ == "__main__":
    main()
