"""Ties at the LIMIT cut: does gold's ORDER BY leave more rows sharing the last kept sort value?"""
import json, os, re, sys, collections
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from executor import execute
HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
test = {json.loads(l)["id"]: json.loads(l) for l in open(os.path.join(HERE, "data/test.jsonl"))}

def real(q): return q.replace("\\n", "\n")
def no_limit(q): return re.sub(r"(?im)^\s*limit\s+\d+\s*$", "", real(q))

cache = {}
def tie_info(ex):
    q = real(ex["cypher"])
    if not re.search(r"(?i)\blimit\b", q) or not re.search(r"(?i)\border\s+by\b", q): return None
    r = execute(ex["graph"], no_limit(q))
    if not isinstance(r, dict) or not r.get("rows"): return None
    rows = r["rows"]; cols = r.get("columns") or []
    k = len(((ex.get("gold_result") or {}).get("rows")) or [])
    if not k or len(rows) <= k: return False
    ob = re.search(r"(?is)\border\s+by\s+(.+?)(?:\n|$)", q)
    keys = []
    if ob:
        for part in ob.group(1).split(","):
            nm = part.strip().split()[0].split(".")[-1]
            for c in cols:
                if c.lower() == nm.lower() and c not in keys: keys.append(c)
    if not keys:
        keys = [c for c in cols if isinstance(rows[0].get(c), (int, float))]
    if not keys: return None
    kf = lambda x: tuple(x.get(c) for c in keys)
    b = kf(rows[k-1])
    return sum(1 for x in rows[k:] if kf(x) == b) > 0

for f, label in [("kimi-k3_v1_plain_n100.json","kimi-k3"),("glm-5p3-flash_v1_plain_n200.json","glm-5p3-flash"),
                 ("glm-5p3_v1_plain_n100.json","glm-5p3 large"),("train_sft.json","30B + SFT")]:
    p = os.path.join(HERE, "results_v2", f)
    if not os.path.exists(p): continue
    d = json.load(open(p)); wrong = [r for r in d["rows"] if not r.get("correct")]
    tied = checked = 0
    for r in wrong:
        ex = test.get(r["id"])
        if not ex: continue
        if r["id"] not in cache: cache[r["id"]] = tie_info(ex)
        v = cache[r["id"]]
        if v is None: continue
        checked += 1; tied += bool(v)
    n = len(d["rows"])
    print(f"{label:15s} n={n:4d} acc={d['accuracy']:5.1%} wrong={len(wrong):3d} order+limit_wrong={checked:3d} "
          f"tie_at_cut={tied:3d} => if ties forgiven: {(d['accuracy']*n+tied)/n:5.1%}")
