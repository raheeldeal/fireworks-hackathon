"""Is config B really better than config A on the same questions?

  python compare.py results/r1_base.json results/r5_full.json:first     # R1 vs R2 (R5 cut at "first")
  python compare.py results/r5_full.json:repair results/r5_full.json    # R4 vs R5

A file name may end in :<stage> to read a full-harness run as if it had stopped there (metrics.cut).
Questions are paired by id. Reports the accuracy difference with a paired-bootstrap 95% CI and an exact McNemar
test on the questions where the two configs disagree.
"""
import json, math, random, sys

import metrics


def load(spec):
    path, _, stage = spec.partition(":")
    doc = json.load(open(path))
    stage = stage or list(doc["views"])[-1]
    return {r["id"]: metrics.cut(r, stage)["outcome"] == "correct" for r in doc["rows"]}, f"{doc['tag']}:{stage}"


def mcnemar_p(b, c):
    """Exact two-sided McNemar p-value: b = only A right, c = only B right."""
    n = b + c
    if n == 0:
        return 1.0
    tail = sum(math.comb(n, i) for i in range(min(b, c) + 1)) / 2 ** n
    return min(1.0, 2 * tail)


def compare(a, b, resamples=10000, seed=0):
    ids = sorted(set(a) & set(b))
    diffs = [int(b[i]) - int(a[i]) for i in ids]  # +1 where only B is right, -1 where only A is right
    rng = random.Random(seed)
    boot = sorted(sum(rng.choice(diffs) for _ in diffs) / len(diffs) for _ in range(resamples))
    return {"n": len(ids), "acc_a": sum(a[i] for i in ids) / len(ids), "acc_b": sum(b[i] for i in ids) / len(ids),
            "diff": sum(diffs) / len(ids), "ci95": (boot[int(0.025 * resamples)], boot[int(0.975 * resamples) - 1]),
            "only_a": diffs.count(-1), "only_b": diffs.count(1),
            "p_mcnemar": mcnemar_p(diffs.count(-1), diffs.count(1))}


if __name__ == "__main__":
    (a, name_a), (b, name_b) = load(sys.argv[1]), load(sys.argv[2])
    r = compare(a, b)
    print(f"A = {name_a}: {r['acc_a']:.1%}    B = {name_b}: {r['acc_b']:.1%}    (n = {r['n']} paired questions)")
    print(f"B - A = {r['diff']:+.1%}   95% CI [{r['ci95'][0]:+.1%}, {r['ci95'][1]:+.1%}]   "
          f"only A right: {r['only_a']}   only B right: {r['only_b']}   McNemar p = {r['p_mcnemar']:.4f}")
