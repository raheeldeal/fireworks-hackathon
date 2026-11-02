#!/usr/bin/env python3
"""Print misses of a results file: gold vs pred, with missed and extra codes tallied."""
import collections, json, sys
d = json.load(open(sys.argv[1]))
missed, extra = collections.Counter(), collections.Counter()
rows = [r for r in d["rows"] if not r["correct"]]
for r in rows:
    g, p = set(r["label"]), set(r["pred"])
    missed.update(g - p); extra.update(p - g)
print(f"{d['model'].split('/')[-1]} + {d['prompt']}: {len(rows)} / {d['n']} not exact; invalid {d['invalid_outputs']}")
print("most missed  :", missed.most_common(12))
print("most extra   :", extra.most_common(12))
for r in rows[: int(sys.argv[2]) if len(sys.argv) > 2 else 12]:
    g, p = set(r["label"]), set(r["pred"])
    print(f"\n{r['id']} missed={sorted(g-p)} extra={sorted(p-g)} fin={r['finish_reason']}\n  {r['text'][:400]}")
