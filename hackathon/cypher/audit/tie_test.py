"""How many 'wrong' answers are tie-breaking differences under ORDER BY + LIMIT?
A row is tie-affected if the gold query's ORDER BY has ties spanning the LIMIT boundary,
i.e. removing LIMIT shows more rows with the same sort-key value as the last kept row."""
import json, os, re, sys, collections
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from executor import execute

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
test = {json.loads(l)["id"]: json.loads(l) for l in open(os.path.join(HERE, "data/test.jsonl"))}

def strip_limit(q):
    return re.sub(r"(?is)\blimit\s+\d+\s*$", "", q.strip()).strip()

def tie_at_boundary(ex):
    q = ex["cypher"]
    if not re.search(r"(?i)\blimit\b", q) or not re.search(r"(?i)\border\s+by\b", q): return None
    full = execute(ex["graph"], strip_limit(q))
    if not isinstance(full, dict) or not full.get("rows"): return None
    gold = ex.get("gold_result") or {}
    k = len(gold.get("rows") or [])
    if k == 0 or len(full["rows"]) <= k: return False
    # sort key = the columns named in ORDER BY that exist in the result
    cols = full.get("columns") or []
    ob = re.search(r"(?is)\border\s+by\s+(.+?)(?:\s+limit\b|$)", q)
    keys = []
    if ob:
        for part in ob.group(1).split(","):
            name = part.strip().split()[0].split(".")[-1]
            for c in cols:
                if c.lower() == name.lower(): keys.append(c)
    if not keys: keys = [c for c in cols if isinstance(full["rows"][0].get(c), (int, float))]
    if not keys: return None
    def key(r): return tuple(r.get(c) for c in keys)
    boundary = key(full["rows"][k-1])
    after = sum(1 for r in full["rows"][k:] if key(r) == boundary)
    return after > 0

cache = {}
for f, label in [("kimi-k3_v1_plain_n100.json", "kimi-k3"),
                 ("glm-5p3-flash_v1_plain_n200.json", "glm-5p3-flash"),
                 ("glm-5p3_v1_plain_n100.json", "glm-5p3 large"),
                 ("train_sft.json", "30B + SFT")]:
    p = os.path.join(HERE, "results_v2", f)
    if not os.path.exists(p): print(label, "missing"); continue
    d = json.load(open(p))
    wrong = [r for r in d["rows"] if not r.get("correct")]
    tied = 0; checked = 0
    for r in wrong:
        ex = test.get(r["id"])
        if not ex: continue
        if r["id"] not in cache: cache[r["id"]] = tie_at_boundary(ex)
        v = cache[r["id"]]
        if v is None: continue
        checked += 1
        if v: tied += 1
    n = len(d["rows"])
    print(f"{label:16s} n={n:4d} acc={d['accuracy']:5.1%} wrong={len(wrong):3d}  of which tie-at-boundary: {tied:3d}  "
          f"=> ceiling if ties forgiven: {(d['accuracy']*n + tied)/n:5.1%}")
