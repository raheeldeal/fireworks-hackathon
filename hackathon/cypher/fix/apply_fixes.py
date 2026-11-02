#!/usr/bin/env python3
"""Apply human corrections from fix/fix_sheet.csv to produce a human-corrected test set, then re-score
every stored prediction against it offline (no model calls).

  PYTHONPATH=train/.pylib ../runs/regex/venv311/bin/python fix/apply_fixes.py

Outputs:
  data/test_human_v2.jsonl   corrected set (keep + fix rows; drop rows removed), new sha256 in data/TEST_HUMAN_V2_HASH
  fix/CHANGELOG.md           every change: id, verdict, old query, new query, old/new row counts, your note
  fix/RESCORE_HUMAN.md       accuracy of every stored run on the public set vs the corrected set
"""
import csv, hashlib, json, os, sys, glob
HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, HERE)
from executor import execute
from score import score_v2

sheet = list(csv.DictReader(open(os.path.join(HERE, "fix", "fix_sheet.csv"))))
test = {json.loads(l)["id"]: json.loads(l) for l in open(os.path.join(HERE, "data", "test.jsonl"))}

out, log, dropped, fixed, kept = [], [], 0, 0, 0
for r in sheet:
    rid = r["id"]; ex = dict(test[rid]); v = (r.get("VERDICT (keep/fix/drop)") or "keep").strip().lower()
    if v.startswith("drop"):
        dropped += 1; log.append((rid, "drop", ex["cypher"], "", ex.get("gold_n_rows"), "", r.get("YOUR_note", ""))); continue
    if v.startswith("fix"):
        newq = (r.get("CORRECTED_cypher") or "").strip()
        if not newq:
            print(f"{rid}: verdict=fix but CORRECTED_cypher empty; keeping original"); kept += 1; out.append(ex); continue
        res = execute(ex["graph"], newq)
        if not isinstance(res, dict) or not res.get("rows"):
            print(f"{rid}: corrected query failed or returned no rows ({str(res)[:120]}); keeping original"); kept += 1; out.append(ex); continue
        log.append((rid, "fix", ex["cypher"], newq, ex.get("gold_n_rows"), len(res["rows"]), r.get("YOUR_note", "")))
        ex["cypher"] = newq; ex["gold_result"] = res; ex["gold_n_rows"] = len(res["rows"]); ex["human_corrected"] = True
        fixed += 1; out.append(ex); continue
    kept += 1; out.append(ex)

path = os.path.join(HERE, "data", "test_human_v2.jsonl")
with open(path, "w") as f:
    for ex in out: f.write(json.dumps(ex, ensure_ascii=False) + "\n")
h = hashlib.sha256(open(path, "rb").read()).hexdigest()
open(os.path.join(HERE, "data", "TEST_HUMAN_V2_HASH"), "w").write(h + "  data/test_human_v2.jsonl\n")
print(f"kept {kept}, fixed {fixed}, dropped {dropped} -> {len(out)} rows, sha256 {h[:16]}")

with open(os.path.join(HERE, "fix", "CHANGELOG.md"), "w") as f:
    f.write(f"# Human corrections to the locked test set\n\nPublic set sha256 (unchanged): see data/TEST_HASH\nCorrected set sha256: {h}\n\n"
            f"kept {kept}, fixed {fixed}, dropped {dropped}\n\n| id | verdict | old gold | new gold | old rows | new rows | note |\n|---|---|---|---|---|---|---|\n")
    for rid, v, old, new, on, nn, note in log:
        f.write(f"| {rid} | {v} | `{old.replace('|','\\|')[:120]}` | `{new.replace('|','\\|')[:120]}` | {on} | {nn} | {note.replace('|','/')} |\n")

# re-score every stored run: re-execute stored predictions against the live graph, compare with corrected gold
newgold = {ex["id"]: ex for ex in out}
cache = {}
def run(graph, q):
    k = (graph, q)
    if k not in cache: cache[k] = execute(graph, q)
    return cache[k]
lines = ["# Re-score on the human-corrected set\n", "| run | public set | corrected set | Δ |", "|---|---|---|---|"]
for p in sorted(glob.glob(os.path.join(HERE, "results_v2", "*.json"))):
    try: d = json.load(open(p))
    except Exception: continue
    rows = d.get("rows") or []
    if not rows or "pred_cypher" not in rows[0]: continue
    ok = n = 0
    for r in rows:
        ex = newgold.get(r["id"])
        if not ex: continue
        n += 1
        q = r.get("pred_cypher")
        if not q: continue
        res = run(ex["graph"], q)
        st, correct = score_v2(res, ex["gold_result"], ex["cypher"]) if score_v2.__code__.co_argcount >= 3 else score_v2(res, ex["gold_result"])
        ok += bool(correct)
    if n: lines.append(f"| {os.path.basename(p)} | {d.get('accuracy', 0):.1%} | {ok/n:.1%} | {ok/n - d.get('accuracy', 0):+.1%} |")
open(os.path.join(HERE, "fix", "RESCORE_HUMAN.md"), "w").write("\n".join(lines) + "\n")
print("\n".join(lines[:14]))
