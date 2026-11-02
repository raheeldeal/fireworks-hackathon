#!/usr/bin/env python3
"""Re-execute every stored prediction (and every gold query with LIMIT stripped) once, into a
content-addressed cache so v2 scoring is fully offline afterwards. No model calls: $0."""
import json, glob, os, sys, hashlib, logging, threading
from concurrent.futures import ThreadPoolExecutor
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from executor import execute
import score as S
logging.getLogger("neo4j").setLevel(logging.ERROR)

HERE = os.path.dirname(os.path.abspath(__file__))
CACHE = os.environ.get("EXEC_CACHE", os.path.join(HERE, "exec_cache.json"))

def key(graph, cypher):
    return hashlib.sha1((graph + "\x00" + (cypher or "")).encode()).hexdigest()

def load_cache():
    return json.load(open(CACHE)) if os.path.exists(CACHE) else {}

def main():
    cache = load_cache()
    want = {}
    for f in sorted(glob.glob(os.path.join(os.path.dirname(HERE), "results", "*.json"))):
        d = json.load(open(f))
        if not isinstance(d, dict) or "rows" not in d:
            continue
        for r in d["rows"]:
            want[key(r["graph"], r.get("pred_cypher") or "")] = (r["graph"], r.get("pred_cypher") or "")
    # gold with LIMIT stripped, for the LIMIT-tie rule
    for l in open(os.path.join(os.path.dirname(HERE), "data", "test.jsonl")):
        ex = json.loads(l)
        if ex["complexity"]["limit"]:
            nl = S.strip_limit(ex["cypher"])
            want[key(ex["graph"], nl)] = (ex["graph"], nl)
    todo = [(k, v) for k, v in want.items() if k not in cache]
    print(f"{len(want)} wanted, {len(cache)} cached, {len(todo)} to run", flush=True)
    lock = threading.Lock(); done = [0]
    def run(kv):
        k, (g, c) = kv
        r = execute(g, c) if (c or "").strip() else {"ok": False, "rows": [], "columns": [], "error": "no query", "secs": 0.0}
        with lock:
            cache[k] = {"ok": r["ok"], "rows": r["rows"], "columns": r["columns"], "error": r["error"]}
            done[0] += 1
            if done[0] % 200 == 0:
                print(f"  {done[0]}/{len(todo)}", flush=True)
                json.dump(cache, open(CACHE, "w"))
    with ThreadPoolExecutor(12) as pool:
        list(pool.map(run, todo))
    json.dump(cache, open(CACHE, "w"))
    print("cache size", len(cache), "->", CACHE)

if __name__ == "__main__":
    main()
