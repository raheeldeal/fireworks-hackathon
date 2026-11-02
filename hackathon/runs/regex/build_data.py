#!/usr/bin/env python3
"""Build data/test.jsonl and data/train.jsonl for natural-language-to-regex.

Source: nicholaslocascio/deep-regex (MIT), folders datasets/KB13 and datasets/NL-RX-Synth,
downloaded to raw/dl/deep-regex-master/datasets/.

Rows whose gold regex uses the paper's DSL-only operators `&` (intersection) and `~` (negation)
are dropped because they cannot be executed by Python `re`. For every kept row we generate
10 positive strings (exrex + rejection sampling against the gold regex under re.fullmatch) and
10 negative strings (mutations of positives that the gold regex rejects). Rows for which we cannot
find 10 unique positives and 10 unique negatives are dropped.

Test = KB13 (human-written descriptions), one row per unique gold regex, minus hand-excluded ids
listed in data/excluded_gold.txt. Train = remaining KB13 rows + NL-RX-Synth rows, no gold regex or
description shared with test.

Deterministic: fixed seeds; run twice and you get byte-identical files.
Usage: venv/bin/python build_data.py [--n-test 200] [--n-train 500]
"""
import argparse
import json
import os
import random
import re
import string
import sys

import exrex

HERE = os.path.dirname(os.path.abspath(__file__))
RAW = os.path.join(HERE, "raw", "dl", "deep-regex-master", "datasets")
ALPHABET = string.ascii_letters + string.digits + " .,-_'!?:;/@#$%&*+=()[]{}<>\"\\|^`~"


def load(ds):
    src = open(os.path.join(RAW, ds, "src.txt")).read().splitlines()
    tg = open(os.path.join(RAW, ds, "targ.txt")).read().splitlines()
    assert len(src) == len(tg)
    out = []
    for i, (s, t) in enumerate(zip(src, tg)):
        s = s.strip()
        t = t.strip()
        if not s or not t or "&" in t or "~" in t:
            continue
        try:
            re.compile(t)
        except re.error:
            continue
        out.append({"id": f"{ds.lower().replace('-', '')}-{i+1}", "source": ds, "text": s, "gold": t})
    return out


class _Timeout(Exception):
    pass


def enrich_train(r, rng, pool, with_strings, seconds=3):
    """Train rows: strings only when asked, and never more than `seconds` of exrex per row (some golds explode)."""
    if not with_strings:
        return dict(r, positives=[], negatives=[])
    import signal

    def _h(signum, frame):
        raise _Timeout()
    old = signal.signal(signal.SIGALRM, _h)
    signal.alarm(seconds)
    try:
        return enrich(r, rng, pool)
    except _Timeout:
        print(f"train: timeout generating strings for {r['id']}", file=sys.stderr)
        return None
    finally:
        signal.alarm(0)
        signal.signal(signal.SIGALRM, old)


def gen_positives(gold, rng, want=10, tries=400):
    pat = re.compile(gold)
    seen, out = set(), []
    # exrex is seeded through the global random module
    for k in range(tries):
        random.seed(rng.randrange(1 << 30))
        limit = 1 + (k % 6)
        try:
            cand = exrex.getone(gold, limit=limit)
        except Exception:
            return out
        if cand is None or len(cand) > 60:
            continue
        # exrex ignores \b; sometimes swapping punctuation for a space repairs the candidate
        variants = [cand]
        if "\\b" in gold:
            variants.append("".join(" " if (not c.isalnum() and rng.random() < 0.7) else c for c in cand))
        for v in variants:
            if v in seen:
                continue
            if pat.fullmatch(v):
                seen.add(v)
                out.append(v)
                if len(out) >= want:
                    return out
    return out


def mutate(s, rng, pool):
    ops = []
    if s:
        i = rng.randrange(len(s))
        ops += [
            s[:i] + s[i + 1:],                                   # delete
            s[:i] + rng.choice(ALPHABET) + s[i:],                # insert
            s[:i] + rng.choice(ALPHABET) + s[i + 1:],            # replace
            s[:i] + s[i + 1:i + 2] + s[i:i + 1] + s[i + 2:],     # swap adjacent
            s[: max(0, len(s) - 1 - rng.randrange(min(3, len(s))))],  # truncate end
            s[1 + rng.randrange(min(3, len(s))):],               # truncate start
            s.upper(), s.lower(), s.swapcase(),
            s[::-1],
            re.sub(r"\d", "", s),
            re.sub(r"[A-Za-z]", "", s),
            re.sub(r"\s+", "", s),
            s + rng.choice(ALPHABET),
            rng.choice(ALPHABET) + s,
            s + s,
            " ".join(s.split()[1:]) if " " in s else s + " ",
        ]
    ops += ["", rng.choice(pool) if pool else "x", rng.choice(ALPHABET), "".join(rng.choice(ALPHABET) for _ in range(rng.randrange(1, 12)))]
    return ops


def gen_negatives(gold, positives, rng, pool, want=10):
    pat = re.compile(gold)
    seen, out = set(), []
    for _ in range(60):
        base = rng.choice(positives)
        cands = mutate(base, rng, pool)
        rng.shuffle(cands)
        for c in cands:
            if c in seen or len(c) > 80:
                continue
            if not pat.fullmatch(c):
                seen.add(c)
                out.append(c)
                if len(out) >= want:
                    return out
    return out


def enrich(row, pool_rng, pool):
    rng = random.Random(f"{row['id']}|{row['gold']}")
    pos = gen_positives(row["gold"], rng)
    if len(pos) < 10:
        return None
    neg = gen_negatives(row["gold"], pos, rng, pool)
    if len(neg) < 10:
        return None
    row = dict(row)
    row["positives"] = pos
    row["negatives"] = neg
    return row


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--n-test", type=int, default=200)
    ap.add_argument("--n-train", type=int, default=500)
    ap.add_argument("--train-strings", type=int, default=120, help="generate positives/negatives for only the first N train rows (held-out eval); the rest keep text+gold only")
    ap.add_argument("--train-only", action="store_true", help="reuse the existing data/test.jsonl instead of regenerating it")
    ap.add_argument("--test-only", action="store_true")
    args = ap.parse_args()

    excl_path = os.path.join(HERE, "data", "excluded_gold.txt")
    excluded = set()
    if os.path.exists(excl_path):
        for line in open(excl_path):
            line = line.strip()
            if line and not line.startswith("#"):
                excluded.add(line.split()[0])

    kb = load("KB13")
    nl = load("NL-RX-Synth")
    print(f"KB13 usable rows {len(kb)}, NL-RX-Synth usable rows {len(nl)}", file=sys.stderr)

    # one KB13 row per unique gold regex, first occurrence, shuffled with a fixed seed
    rng = random.Random(13)
    seen_gold, seen_text, uniq = set(), set(), []
    for r in kb:
        key = (r["gold"], r["text"].lower())
        if r["gold"] in seen_gold or r["text"].lower() in seen_text:
            continue
        seen_gold.add(r["gold"])
        seen_text.add(r["text"].lower())
        uniq.append(r)
    rng.shuffle(uniq)
    pool = [r["text"] for r in uniq][:50]  # used only as random other-strings for negatives

    os.makedirs(os.path.join(HERE, "data"), exist_ok=True)
    test_path = os.path.join(HERE, "data", "test.jsonl")
    if args.train_only:
        test = [json.loads(l) for l in open(test_path)]
    else:
        test = []
        for r in uniq:
            if len(test) >= args.n_test:
                break
            if r["id"] in excluded:
                continue
            e = enrich(r, rng, pool)
            if e is None:
                print(f"drop (no strings) {r['id']} {r['gold']!r}", file=sys.stderr)
                continue
            test.append(e)
        with open(test_path, "w") as f:
            for r in test:
                f.write(json.dumps(r, ensure_ascii=False) + "\n")
        print(f"wrote data/test.jsonl with {len(test)} rows", file=sys.stderr)
    if args.test_only:
        return
    test_ids = {r["id"] for r in test}
    rest = [r for r in uniq if r["id"] not in test_ids]  # same list whether or not test.jsonl was regenerated
    rng = random.Random(31)  # train RNG is independent of the test RNG so --train-only reproduces the full run

    test_gold = {r["gold"] for r in test}
    test_text = {r["text"].lower() for r in test}
    train = []
    for r in rest:  # remaining KB13 rows (dedup'd)
        if r["gold"] in test_gold or r["text"].lower() in test_text or r["id"] in excluded:
            continue
        e = enrich_train(r, rng, pool, len(train) < args.train_strings)
        if e:
            train.append(e)
    rng2 = random.Random(29)
    rng2.shuffle(nl)
    seen_nl = set()
    for r in nl:
        if len(train) >= args.n_train:
            break
        if r["gold"] in test_gold or r["gold"] in seen_nl or r["text"].lower() in test_text:
            continue
        e = enrich_train(r, rng2, pool, len(train) < args.train_strings)
        if e:
            seen_nl.add(r["gold"])
            train.append(e)
    with open(os.path.join(HERE, "data", "train.jsonl"), "w") as f:
        for r in train:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    heldout = [r for r in train if r["positives"]][:100]
    with open(os.path.join(HERE, "data", "heldout.jsonl"), "w") as f:
        for r in heldout:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    print(f"wrote data/heldout.jsonl with {len(heldout)} rows (train rows with strings, for prompt sanity checks)", file=sys.stderr)
    print(f"wrote data/train.jsonl with {len(train)} rows "
          f"({sum(r['source']=='KB13' for r in train)} KB13, {sum(r['source']!='KB13' for r in train)} NL-RX-Synth)", file=sys.stderr)


if __name__ == "__main__":
    main()
