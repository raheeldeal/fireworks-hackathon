#!/usr/bin/env python3
"""Re-score every results/*.json offline with score_v2, from stored pred_cypher plus the
execution cache built by build_cache.py. No model calls, so $0 of new spend.

  .venv/bin/python audit/rescore.py            # writes results_v2/*.json and audit/RESCORE.md
  .venv/bin/python audit/rescore.py --dump-misses glm-5p3-flash_v1_plain_n200
"""
import argparse, glob, json, os, sys, collections
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import score as S
from build_cache import key, load_cache

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
GOLD_DEFECTS = ["t020", "t047", "t083", "t138"]  # gold uses properties absent from the graph

EX = {}
for _l in open(os.path.join(ROOT, "data", "test.jsonl")):
    _e = json.loads(_l)
    EX[_e["id"]] = _e
CACHE = load_cache()
EMPTY = {"ok": False, "rows": [], "columns": [], "error": "not executed"}


def pred_result(graph, cypher):
    if not graph or not (cypher or "").strip():
        return {"ok": False, "rows": [], "columns": [], "error": "no query"}
    return CACHE.get(key(graph, cypher), EMPTY)


def gold_result(ex):
    return {"ok": True, **ex["gold_result"]}


def gold_unlimited(ex):
    if not ex["complexity"]["limit"]:
        return None
    return CACHE.get(key(ex["graph"], S.strip_limit(ex["cypher"])))


def v2_row(row):
    ex = EX.get(row["id"])
    if ex is None:
        return None
    pr = pred_result(ex["graph"], row.get("pred_cypher"))
    return S.score_v2(gold_result(ex), pr, ex["cypher"], gold_unlimited(ex))


def rescore_file(path):
    d = json.load(open(path))
    if not isinstance(d, dict) or "rows" not in d or not d["rows"]:
        return None
    rows, n_missing = [], 0
    for r in d["rows"]:
        v = v2_row(r)
        if v is None:
            n_missing += 1
            continue
        nr = dict(r)
        nr["exec_status_v1"] = r.get("exec_status")
        nr["exec_status_v2"] = v
        nr["correct_v1"] = bool(r.get("correct"))
        nr["correct_v2"] = v == "correct"
        nr["exec_status"] = v
        nr["correct"] = v == "correct"
        nr["gold_defect"] = r["id"] in GOLD_DEFECTS
        rows.append(nr)
    n = len(rows)
    clean = [r for r in rows if not r["gold_defect"]]

    def agg(rs):
        if not rs:
            return None
        return {"n": len(rs),
                "accuracy_v1": round(sum(r["correct_v1"] for r in rs) / len(rs), 4),
                "accuracy_v2": round(sum(r["correct_v2"] for r in rs) / len(rs), 4)}

    out = {k: v for k, v in d.items() if k != "rows"}
    out.update({
        "scorer": "score_v2 (audit/SCORING.md)",
        "n": n,
        "accuracy_v1": round(sum(r["correct_v1"] for r in rows) / n, 4),
        "accuracy": round(sum(r["correct_v2"] for r in rows) / n, 4),
        "accuracy_v2": round(sum(r["correct_v2"] for r in rows) / n, 4),
        "accuracy_v2_excl_gold_defects": round(sum(r["correct_v2"] for r in clean) / len(clean), 4),
        "error_rate": round(sum(r["exec_status_v2"] == "error" for r in rows) / n, 4),
        "empty_rate": round(sum(r["exec_status_v2"] == "empty" for r in rows) / n, 4),
        "wrong_rate": round(sum(r["exec_status_v2"] == "wrong" for r in rows) / n, 4),
        "by_tier_v2": {t: agg([r for r in rows if r.get("tier") == t]) for t in ("easy", "medium", "hard")},
        "by_graph_v2": {g: agg([r for r in rows if r.get("graph") == g])
                        for g in sorted({r.get("graph") for r in rows if r.get("graph")})},
        "rows_not_scored": n_missing,
        "rows": rows,
    })
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dump-misses", default="")
    ap.add_argument("--limit", type=int, default=40)
    args = ap.parse_args()

    if args.dump_misses:
        dump(args.dump_misses, args.limit)
        return

    os.makedirs(os.path.join(ROOT, "results_v2"), exist_ok=True)
    table, skipped = [], []
    for p in sorted(glob.glob(os.path.join(ROOT, "results", "*.json"))):
        name = os.path.basename(p)
        out = rescore_file(p)
        if out is None:
            skipped.append(name)
            continue
        if out["accuracy_v1"] == 0.0 and out["error_rate"] == 1.0:
            skipped.append(name + " (dead run: no predictions)")
            continue
        json.dump(out, open(os.path.join(ROOT, "results_v2", name), "w"), indent=1, default=str)
        table.append((name, out))
    write_rescore_md(table, skipped)
    for name, o in table:
        print(f"{name[:44]:44s} v1 {o['accuracy_v1']:6.1%}  v2 {o['accuracy_v2']:6.1%}  "
              f"delta {o['accuracy_v2']-o['accuracy_v1']:+.1%}")
    print("skipped:", skipped)


def write_rescore_md(table, skipped):
    L = ["# Re-score: v1 strict vs v2 execution accuracy",
         "",
         "Every file in `results/` re-scored offline from its stored `pred_cypher` (re-executed once",
         "against the live demo graphs and cached in `audit/exec_cache.json`). No model calls; new spend $0.",
         "v2 rules and justifications: `audit/SCORING.md`. Per-row v2 verdicts: `results_v2/<same name>.json`.",
         "",
         "`v2 (clean)` drops the 4 known gold-defect rows (t020, t047, t083, t138), whose gold returns 0/null",
         "because the gold query reads properties the graph does not have; on those rows a broken prediction",
         "can score correct, so the clean column is the number to quote.",
         "",
         "| config | n | v1 acc | v2 acc | delta | v2 (clean, n=196) | v2 error | v2 empty |",
         "|---|---|---|---|---|---|---|---|"]
    for name, o in table:
        L.append(f"| {name.replace('.json','')} | {o['n']} | {o['accuracy_v1']:.1%} | {o['accuracy_v2']:.1%} | "
                 f"{100*(o['accuracy_v2']-o['accuracy_v1']):+.1f} pp | {o['accuracy_v2_excl_gold_defects']:.1%} | "
                 f"{o['error_rate']:.1%} | {o['empty_rate']:.1%} |")
    L += ["", "## Per-tier (easy 70 / medium 87 / hard 43 on the 200-row set; the n=100 files cover",
          "the first 100 rows, so their tier counts are smaller but the pattern is the same)", "",
          "| config | easy v1 | easy v2 | medium v1 | medium v2 | hard v1 | hard v2 | monotone easy>=med>=hard? |",
          "|---|---|---|---|---|---|---|---|"]
    mono = 0
    tot = 0
    for name, o in table:
        bt = o["by_tier_v2"]
        if not all(bt.get(t) for t in ("easy", "medium", "hard")):
            continue
        e, m, h = (bt[t]["accuracy_v2"] for t in ("easy", "medium", "hard"))
        ok = e >= m >= h
        mono += ok
        tot += 1
        L.append(f"| {name.replace('.json','')} | {bt['easy']['accuracy_v1']:.1%} | {e:.1%} | "
                 f"{bt['medium']['accuracy_v1']:.1%} | {m:.1%} | {bt['hard']['accuracy_v1']:.1%} | {h:.1%} | "
                 f"{'yes' if ok else 'NO'} |")
    L += ["", f"Monotone (easy >= medium >= hard) under v2: **{mono} of {tot} configs**.", "",
          "## THE SANITY CHECK STILL FAILS. Read this before quoting any tier number.", "",
          f"Only {mono} of {tot} configs satisfy easy >= medium >= hard under v2 (the one that does is the",
          "gold self-run at 100%). v2 lifts the easy tier by 4 to 8 points, more than any other tier,",
          "but easy remains the **worst** tier for every model. We did not add rules until the check",
          "passed, because the audit says the check is testing the wrong thing:",
          "",
          "**`tier` is not a difficulty label.** `score.complexity()` assigns `easy` to any gold query",
          "with one hop and no aggregation. In this dataset that selects the rows whose questions are",
          "the *least specified*, not the least difficult: bare lookups where the gold author freely",
          "chose the projection (`RETURN m` vs `RETURN m.title` vs `RETURN m.title, m.votes`) and freely",
          "invented an ordering for \"first 3\". Medium and hard questions name their aggregate (\"how",
          "many\", \"the average\", \"top 5 by X\"), which pins the projection and removes that freedom.",
          "",
          "The hand audit (`MISS_AUDIT.md`) measured this on 36 easy misses: 2 are real model errors,",
          "20 are scoring artifacts (15 of them projection-only, which v2 deliberately does not excuse),",
          "11 are gold defects and 7 are ambiguous questions. So easy-tier accuracy is mostly measuring",
          "gold-projection noise. Three honest options, for a human:",
          "",
          "1. Quote overall v2 accuracy and **stop reporting the tier breakdown as a difficulty curve**.",
          "2. Relabel the tiers from the *question* (does it name a count, an order, a projection?)",
          "   rather than from the gold Cypher's shape.",
          "3. Fix the gold projections in a future test set; `data/test.jsonl` is frozen here by",
          "   `data/TEST_HASH`, so this cannot be done in this submission.",
          ""]
    if skipped:
        L += ["Skipped: " + ", ".join(skipped), ""]
    open(os.path.join(HERE, "RESCORE.md"), "w").write("\n".join(L) + "\n")


def dump(name, limit):
    """Print the rows this run gets wrong, easy tier first, for hand classification."""
    d = json.load(open(os.path.join(ROOT, "results", name if name.endswith(".json") else name + ".json")))
    order = {"easy": 0, "medium": 1, "hard": 2}
    miss = [r for r in d["rows"] if not r.get("correct")]
    miss.sort(key=lambda r: (order.get(r.get("tier"), 9), r["id"]))
    for r in miss[:limit]:
        ex = EX[r["id"]]
        pr = pred_result(ex["graph"], r.get("pred_cypher"))
        gu = gold_unlimited(ex)
        print("=" * 100)
        print(f"{r['id']}  tier={r['tier']}  graph={r['graph']}  v1={r.get('exec_status')}  v2={v2_row(r)}")
        print("Q      :", ex["question"])
        print("GOLD   :", ex["cypher"].replace("\\n", " "))
        print("GOLDROW:", json.dumps(ex["gold_result"]["rows"])[:600])
        print("PRED   :", (r.get("pred_cypher") or "").replace("\n", " ")[:400])
        print("PREDROW:", ("ERR " + str(pr.get("error"))[:200]) if not pr["ok"]
              else f"n={len(pr['rows'])} " + json.dumps(pr["rows"])[:600])
        if gu and gu.get("ok"):
            print("GOLDUNL:", f"n={len(gu['rows'])} " + json.dumps(gu["rows"])[:300])
    print(f"\n[{len(miss)} total misses; showed {min(limit, len(miss))}]")


if __name__ == "__main__":
    main()
