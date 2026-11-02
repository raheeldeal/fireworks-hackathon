#!/usr/bin/env python3
"""Read the filled labeling_sheet.csv and report inter-annotator agreement and the noise ceiling.

  python3 agreement.py [labeling_sheet.csv] [--test ../data/test.jsonl]

Each annotator writes one tool name (from candidate_tools) in annotator_A / annotator_B. Blank cells are
reported as unfilled and excluded. The gold comes from the locked test set, never from the sheet.

Definitions:
  agreement rate     rows where A == B, over rows both filled
  ambiguous row      both annotators agree with each other and disagree with gold (label is likely wrong),
                     OR the annotators disagree with each other (two careful readers cannot settle it)
  noise ceiling      1 - ambiguous_rows / N_test. Every row not on the sheet was answered correctly by every
                     strong model config, so it is treated as unambiguous. A model cannot be expected to
                     score above the ceiling on this test set.
"""
import argparse, csv, json, os

HERE = os.path.dirname(os.path.abspath(__file__))


def norm(s):
    return (s or "").strip().lower()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("sheet", nargs="?", default=os.path.join(HERE, "labeling_sheet.csv"))
    ap.add_argument("--test", default=os.path.join(HERE, "..", "data", "test.jsonl"))
    args = ap.parse_args()

    gold = {r["id"]: r["label"] for r in (json.loads(l) for l in open(args.test) if l.strip())}
    n_test = len(gold)
    rows = list(csv.DictReader(open(args.sheet, newline="")))
    filled = [r for r in rows if norm(r["annotator_A"]) and norm(r["annotator_B"])]
    unfilled = [r["id"] for r in rows if r not in filled]
    bad = [(r["id"], c) for r in filled for c in ("annotator_A", "annotator_B")
           if norm(r[c]) not in {norm(x) for x in r["candidate_tools"].split("|")}]

    agree = [r for r in filled if norm(r["annotator_A"]) == norm(r["annotator_B"])]
    both_vs_gold = [r for r in agree if norm(r["annotator_A"]) != norm(gold[r["id"]])]
    split = [r for r in filled if norm(r["annotator_A"]) != norm(r["annotator_B"])]
    a_vs_gold = sum(norm(r["annotator_A"]) == norm(gold[r["id"]]) for r in filled)
    b_vs_gold = sum(norm(r["annotator_B"]) == norm(gold[r["id"]]) for r in filled)
    ambiguous = {r["id"] for r in both_vs_gold} | {r["id"] for r in split}

    print(f"sheet: {len(rows)} rows, {len(filled)} filled by both annotators" + (f", unfilled: {', '.join(unfilled)}" if unfilled else ""))
    for i, c in bad:
        print(f"  warning: {i} {c} is not one of the row's candidate_tools")
    if not filled:
        print("nothing to score yet"); return
    print(f"agreement rate (A == B): {len(agree)}/{len(filled)} = {len(agree)/len(filled):.1%}")
    print(f"A vs gold: {a_vs_gold}/{len(filled)} = {a_vs_gold/len(filled):.1%}   B vs gold: {b_vs_gold}/{len(filled)} = {b_vs_gold/len(filled):.1%}")
    print(f"\nrows where BOTH annotators disagree with gold (likely label errors): {len(both_vs_gold)}")
    for r in both_vs_gold:
        print(f"  {r['id']}: gold={gold[r['id']]}  annotators={r['annotator_A']}  | {r['request_text'][:80]}")
    print(f"\nrows where annotators disagree with each other (genuinely ambiguous): {len(split)}")
    for r in split:
        print(f"  {r['id']}: gold={gold[r['id']]}  A={r['annotator_A']}  B={r['annotator_B']}  | {r['request_text'][:80]}")
    ceiling = 1 - len(ambiguous) / n_test
    print(f"\nambiguous rows: {len(ambiguous)} of {n_test}")
    print(f"noise ceiling: 1 - {len(ambiguous)}/{n_test} = {ceiling:.1%}")
    print(f'\nsentence: "Two annotators labeled the {len(filled)} hardest rows independently (agreement {len(agree)/len(filled):.0%}); '
          f'{len(ambiguous)} of {n_test} test rows are ambiguous or mislabeled, so the ceiling on this test set is {ceiling:.1%}."')


if __name__ == "__main__":
    main()
