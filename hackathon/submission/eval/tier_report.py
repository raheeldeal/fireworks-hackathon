#!/usr/bin/env python3
"""Accuracy per difficulty tier for any results file with the standard `rows` shape (id, correct, pred).

  python3 tier_report.py <results.json> [more.json ...] [--tiers tiers.json]
"""
import argparse, json, os

HERE = os.path.dirname(os.path.abspath(__file__))


def report(path, by_id):
    d = json.load(open(path))
    rows = d["rows"] if isinstance(d, dict) else d
    tally = {"easy": [0, 0], "medium": [0, 0], "hard": [0, 0]}
    unknown = 0
    for r in rows:
        t = by_id.get(r["id"])
        if t is None:
            unknown += 1; continue
        tally[t][0] += bool(r["correct"]); tally[t][1] += 1
    n = sum(v[1] for v in tally.values()); c = sum(v[0] for v in tally.values())
    name = d.get("model", "").split("/")[-1] + " " + d.get("tag", "") if isinstance(d, dict) else os.path.basename(path)
    print(f"{os.path.basename(path)}  ({name.strip()})")
    for t in ("easy", "medium", "hard"):
        k, m = tally[t]
        print(f"  {t:7s} {k:4d}/{m:<4d} {k/m:6.1%}" if m else f"  {t:7s}    -/-     n/a")
    print(f"  {'all':7s} {c:4d}/{n:<4d} {c/n:6.1%}" + (f"   ({unknown} rows not in tiers.json, skipped)" if unknown else ""))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("results", nargs="+")
    ap.add_argument("--tiers", default=os.path.join(HERE, "tiers.json"))
    args = ap.parse_args()
    by_id = json.load(open(args.tiers))["by_id"]
    for p in args.results:
        report(p, by_id)


if __name__ == "__main__":
    main()
