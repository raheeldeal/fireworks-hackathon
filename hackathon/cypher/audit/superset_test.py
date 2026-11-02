"""Superset scoring: prediction must CONTAIN gold's answer columns (extra cols OK, missing NOT OK)."""
import json, glob, os, itertools, collections, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from executor import execute

def norm(v):
    if isinstance(v, float): return round(v, 3)
    if isinstance(v, dict): return tuple(sorted((k, norm(x)) for k, x in v.items()))
    if isinstance(v, list): return tuple(sorted(map(str, (norm(x) for x in v))))
    return v

def cols_of(res):
    if not isinstance(res, dict): return [], []
    return res.get("columns") or [], res.get("rows") or []

def superset_correct(gold, pred):
    gc, gr = cols_of(gold); pc, pr = cols_of(pred)
    if not gr or len(gr) != len(pr) or len(pc) < len(gc): return False
    gvals = [tuple(norm(r.get(c)) for c in gc) for r in gr]
    for combo in itertools.permutations(pc, len(gc)):
        pvals = [tuple(norm(r.get(c)) for c in combo) for r in pr]
        if collections.Counter(gvals) == collections.Counter(pvals): return True
    return False

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
test = {json.loads(l)["id"]: json.loads(l) for l in open(os.path.join(HERE, "data/test.jsonl"))}
cache = {}
def pred_result(graph, q):
    k = (graph, q)
    if k not in cache: cache[k] = execute(graph, q)
    return cache[k]

for f, label in [("kimi-k3_v1_plain_n100.json", "kimi-k3 (frontier)"),
                 ("glm-5p3-flash_v1_plain_n200.json", "glm-5p3-flash (small)"),
                 ("train_base.json", "30B base"),
                 ("train_sft.json", "30B + SFT"),
                 ("train_rft_r1_reject.json", "30B + SFT + RFT"),
                 ("harness_route_big.json", "small + harness (route)")]:
    p = os.path.join(HERE, "results_v2", f)
    if not os.path.exists(p): print(label, "missing"); continue
    d = json.load(open(p)); ok = n = flipped = 0
    for r in d["rows"]:
        ex = test.get(r["id"])
        if not ex: continue
        n += 1
        if r.get("correct"): ok += 1; continue
        q = r.get("pred_cypher")
        if not q: continue
        res = pred_result(ex["graph"], q)
        if isinstance(res, dict) and superset_correct(ex.get("gold_result"), res):
            ok += 1; flipped += 1
    print(f"{label:26s} n={n:4d}  v2={d['accuracy']:6.1%}  superset={ok/n:6.1%}  (+{flipped} rows)")
