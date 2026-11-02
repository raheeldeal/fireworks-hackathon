#!/usr/bin/env python3
"""Build hard_slice.jsonl, labeling_sheet.csv and tiers.json from last night's per-row result files.

Offline, no API calls. Deterministic (seed 7).
  python3 build_slices.py [--results ../../runs/mcp-tool-pick/results] [--strong 0.90] [--min_acc 0.50]

Inputs:  every <model>__<config>__s<seed>.json in the results dir (route__*.json are offline simulations
         built from two other files, so they are skipped: they add no new model predictions).
Outputs: hard_slice.jsonl    rows any strong config (accuracy >= --strong) got wrong, plus 10 control rows
                             every strong config got right, shuffled. Fields: id, text, gold, candidate_tools,
                             kind (miss|control), n_strong_wrong, wrong_in (config names).
         labeling_sheet.csv  the same rows WITHOUT the gold or the kind: id, request_text, candidate_tools,
                             annotator_A, annotator_B, notes. Two humans fill annotator_A / annotator_B independently.
                             candidate_tools = gold + every tool a strong config predicted, padded to at least 3
                             with same-server siblings so a row with one obvious candidate does not give itself away.
         tiers.json          {"easy": [...], "medium": [...], "hard": [...], "by_id": {id: tier}, ...}
                             Population: configs with accuracy >= --min_acc (drops the one degenerate ranked-list run
                             at 6%, which failed on output format, not routing). easy = every config in the population
                             that scored the row got it right; hard = fewer than half did; medium = the rest.
"""
import argparse, csv, glob, json, os, random

HERE = os.path.dirname(os.path.abspath(__file__))
TEST = os.path.join(HERE, "..", "data", "test.jsonl")
CATALOG = os.path.join(HERE, "..", "data", "catalog.json")
MIN_CANDIDATES = 3


def load_results(results_dir):
    out = []
    for p in sorted(glob.glob(os.path.join(results_dir, "*.json"))):
        name = os.path.basename(p)[:-5]
        if name.startswith("route__"):
            continue
        d = json.load(open(p))
        if "rows" not in d or "accuracy" not in d:
            continue
        out.append((name, d))
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--results", default=os.path.join(HERE, "..", "..", "runs", "mcp-tool-pick", "results"))
    ap.add_argument("--strong", type=float, default=0.90)
    ap.add_argument("--min_acc", type=float, default=0.50)
    ap.add_argument("--controls", type=int, default=10)
    ap.add_argument("--seed", type=int, default=7)
    args = ap.parse_args()

    test = [json.loads(l) for l in open(TEST) if l.strip()]
    by_id = {r["id"]: r for r in test}
    catalog = json.load(open(CATALOG))
    siblings = {}
    for t in catalog:
        siblings.setdefault(t["server"], []).append(t["name"])
    configs = load_results(args.results)
    strong = [(n, d) for n, d in configs if d["accuracy"] >= args.strong]
    print(f"{len(configs)} model configs, {len(strong)} strong (accuracy >= {args.strong:.0%}):")
    for n, d in strong:
        print(f"  {n:50s} {d['accuracy']:.1%}  n={d['n']}")

    # per-id tallies
    strong_scored = {i: 0 for i in by_id}
    strong_right = {i: 0 for i in by_id}
    strong_wrong = {i: [] for i in by_id}
    preds = {i: set() for i in by_id}   # predictions by strong configs (valid catalog names only)
    tier_scored = {i: 0 for i in by_id}
    tier_right = {i: 0 for i in by_id}
    for name, d in configs:
        is_strong = d["accuracy"] >= args.strong
        in_tier_pop = d["accuracy"] >= args.min_acc
        for row in d["rows"]:
            i = row["id"]
            if i not in by_id:
                continue
            if in_tier_pop:
                tier_scored[i] += 1
                tier_right[i] += bool(row["correct"])
            if is_strong:
                strong_scored[i] += 1
                if row["correct"]:
                    strong_right[i] += 1
                else:
                    strong_wrong[i].append(name)
                if row["pred"] != "invalid":
                    preds[i].add(row["pred"])

    rng = random.Random(args.seed)
    misses = [i for i in by_id if strong_wrong[i]]
    all_right = [i for i in by_id if strong_scored[i] and strong_right[i] == strong_scored[i]]
    controls = rng.sample(sorted(all_right), args.controls)

    rows = []
    for i in misses + controls:
        gold = by_id[i]["label"]
        cands = preds[i] | {gold}
        pool = [s for s in siblings[gold.split(".")[0]] if s not in cands]
        rng.shuffle(pool)
        while len(cands) < MIN_CANDIDATES and pool:
            cands.add(pool.pop())
        cands = sorted(cands)
        rng.shuffle(cands)
        rows.append({"id": i, "text": by_id[i]["text"], "gold": gold, "candidate_tools": cands,
                     "kind": "miss" if i in misses else "control",
                     "n_strong_wrong": len(strong_wrong[i]), "wrong_in": strong_wrong[i]})
    rng.shuffle(rows)
    with open(os.path.join(HERE, "hard_slice.jsonl"), "w") as f:
        for r in rows:
            f.write(json.dumps(r) + "\n")
    with open(os.path.join(HERE, "labeling_sheet.csv"), "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["id", "request_text", "candidate_tools", "annotator_A", "annotator_B", "notes"])
        for r in rows:
            w.writerow([r["id"], r["text"], " | ".join(r["candidate_tools"]), "", "", ""])
    print(f"hard slice: {len(misses)} rows missed by a strong config + {len(controls)} controls = {len(rows)} rows")

    # tiers
    pop = [n for n, d in configs if d["accuracy"] >= args.min_acc]
    tiers = {"easy": [], "medium": [], "hard": []}
    for i in sorted(by_id):
        frac = tier_right[i] / tier_scored[i] if tier_scored[i] else 0
        t = "easy" if tier_right[i] == tier_scored[i] else ("hard" if frac < 0.5 else "medium")
        tiers[t].append(i)
    tiers["by_id"] = {i: t for t in ("easy", "medium", "hard") for i in tiers[t]}
    tiers["n_configs"] = len(pop)
    tiers["configs"] = pop
    tiers["rule"] = (f"population: {len(pop)} model configs with accuracy >= {args.min_acc:.0%} (route__ simulations and "
                     f"degenerate runs excluded); easy: every config that scored the row got it right; hard: fewer than half did; medium: the rest")
    json.dump(tiers, open(os.path.join(HERE, "tiers.json"), "w"), indent=1)
    print(f"tiers over {len(pop)} configs: easy {len(tiers['easy'])}, medium {len(tiers['medium'])}, hard {len(tiers['hard'])}")


if __name__ == "__main__":
    main()
