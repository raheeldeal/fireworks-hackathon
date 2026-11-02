#!/usr/bin/env python3
"""Keyword-overlap retriever: pick the top-K catalog tools for a request. Stdlib only, deterministic."""
import json, math, re, os, collections
HERE = os.path.dirname(os.path.abspath(__file__))
STOP = set("a an the to for of in on at by with from and or is are be my our your me i we you it this that please can could would will just into out up down as if so then than there here about any some all one two new old".split())
def toks(s):
    out = []
    for w in re.findall(r"[a-z0-9]+", s.lower()):
        if w in STOP or len(w) < 2: continue
        for suf in ("ing", "ed", "es", "s"):
            if w.endswith(suf) and len(w) - len(suf) >= 3: w = w[: -len(suf)]; break
        out.append(w)
    return out
class Retriever:
    def __init__(self, catalog=None):
        self.cat = catalog or json.load(open(os.path.join(HERE, "data", "catalog.json")))
        self.docs = [set(toks(t["name"].replace(".", " ").replace("_", " ") + " " + t["description"])) for t in self.cat]
        df = collections.Counter(w for d in self.docs for w in d)
        n = len(self.docs)
        self.idf = {w: math.log((n + 1) / (c + 0.5)) for w, c in df.items()}
    def top(self, text, k=10):
        q = set(toks(text))
        scored = []
        for t, d in zip(self.cat, self.docs):
            s = sum(self.idf.get(w, 0.0) for w in q & d)
            scored.append((s, t))
        scored.sort(key=lambda x: (-x[0], x[1]["name"]))
        return [t for s, t in scored[:k]]
if __name__ == "__main__":
    import sys
    r = Retriever(); k = int(sys.argv[1]) if len(sys.argv) > 1 else 10
    for split in ("test", "train"):
        rows = [json.loads(l) for l in open(os.path.join(HERE, "data", f"{split}.jsonl"))]
        hit = sum(any(t["name"] == row["label"] for t in r.top(row["text"], k)) for row in rows)
        hit1 = sum(r.top(row["text"], 1)[0]["name"] == row["label"] for row in rows)
        print(f"{split}: recall@{k} {hit/len(rows):.3f}  top1 {hit1/len(rows):.3f}  (n={len(rows)})")
