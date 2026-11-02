"""Print BASELINES.md tables from results/*.json (excludes smoke/ and gold)."""
import json, glob, os, csv
HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
files = sorted(glob.glob(os.path.join(HERE, "results", "*.json")))
res = [json.load(open(f)) for f in files]
res = [r for r in res if r["model"] != "gold"]
res.sort(key=lambda r: -r["accuracy"])
short = lambda m: m.split("/")[-1]
L = []
L.append("| model | config | n | accuracy (strict) | accuracy (lenient) | wrong | error | empty | p50 s | p95 s | $/1k | out tok/row | reasoning tok/row |")
L.append("|---|---|---|---|---|---|---|---|---|---|---|---|---|")
for r in res:
    L.append(f"| {short(r['model'])} | {r['prompt']} | {r['n']} | {r['accuracy']:.1%} | {r.get('accuracy_lenient',float('nan')):.1%} | {r['wrong_rate']:.1%} | {r['error_rate']:.1%} | {r['empty_rate']:.1%} | "
             f"{r['p50_latency_s']:.2f} | {r['p95_latency_s']:.2f} | ${r['cost_per_1k_requests_usd']:.3f} | {r['out_tokens']//r['n']} | {r['reasoning_tokens']//r['n']} |")
graphs = ["movies", "recommendations", "northwind", "fincen", "twitter"]
L.append("\n**Accuracy by graph**\n")
L.append("| model | n | " + " | ".join(graphs) + " |"); L.append("|---|---|" + "---|" * len(graphs))
for r in res:
    L.append(f"| {short(r['model'])} | {r['n']} | " + " | ".join(f"{r['by_graph'][g]['accuracy']:.0%} ({r['by_graph'][g]['n']})" if g in r['by_graph'] else "-" for g in graphs) + " |")
L.append("\n**Accuracy by complexity tier** (easy: 0 to 1 hop, no aggregation; medium: multi-hop or aggregation; hard: both)\n")
L.append("| model | easy | medium | hard |"); L.append("|---|---|---|---|")
for r in res:
    L.append(f"| {short(r['model'])} | " + " | ".join(f"{r['by_tier'][t]['accuracy']:.0%} ({r['by_tier'][t]['n']})" if t in r['by_tier'] else "-" for t in ["easy", "medium", "hard"]) + " |")
# same-100 comparison: all models on the first 100 rows
first100 = {json.loads(l)["id"] for i, l in enumerate(open(os.path.join(HERE, "data", "test.jsonl"))) if i < 100}
L.append("\n**Apples to apples: all models on the same first 100 test rows**\n")
L.append("| model | strict (first 100) | lenient (first 100) |"); L.append("|---|---|---|")
for r in res:
    rs = [x for x in r["rows"] if x["id"] in first100]
    if len(rs) == 100:
        L.append(f"| {short(r['model'])} | {sum(x['correct'] for x in rs)/100:.0%} | {sum(x.get('lenient_status')=='correct' for x in rs)/100:.0%} |")
# oracle / headroom
byid = {}
for r in res:
    for x in r["rows"]:
        byid.setdefault(x["id"], []).append(x["correct"])
f100 = [v for k, v in byid.items() if k in first100]
L.append(f"\nOn the first 100 rows, {sum(all(not c for c in v) for v in f100)} rows are missed by every model; "
         f"{sum(any(c for c in v) for v in f100)} are solved by at least one model (oracle ceiling).")
spent = sum(float(x["cost"]) for x in csv.DictReader(open(os.path.join(HERE, "ledger.csv"))))
L.append(f"\nLedger total: ${spent:.4f}")
print("\n".join(L))
