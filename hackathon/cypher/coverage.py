#!/usr/bin/env python3
"""Coverage-accuracy curve: with the vote agreement signal, answer only when confident.
Reports precision among answered, coverage, and cost per correct answer."""
import glob, json, os, collections

def load(p):
    d = json.load(open(p)); return d
# pool all vote runs for agreement -> correctness
runs = [load(p) for p in sorted(glob.glob("results/harness_vote3*.json"))]
if not runs: raise SystemExit("no vote runs")
by_agree = collections.defaultdict(list)
for d in runs:
    for r in d["rows"]:
        a = r.get("agreement")
        if a is None: continue
        by_agree[a].append(bool(r.get("correct")))
order = sorted(by_agree, key=lambda a: -(a if isinstance(a,int) else 0))
print(f"{'policy':34s} {'coverage':>9s} {'precision':>10s} {'answered_correct_of_200':>24s}")
print("-"*82)
cum_t = cum_c = 0
total = sum(len(v) for v in by_agree.values())
rows_out=[]
for a in order:
    v = by_agree[a]; cum_t += len(v); cum_c += sum(v)
    cov = cum_t/total; prec = cum_c/cum_t
    label = {3:"answer only if 3/3 agree",2:"answer if >=2/3 agree"}.get(a, "answer everything")
    print(f"{label:34s} {cov:9.1%} {prec:10.1%} {cum_c/len(runs):24.0f}")
    rows_out.append({"policy":label,"coverage":round(cov,4),"precision":round(prec,4)})
json.dump(rows_out, open("results/coverage_curve.json","w"), indent=2)
# cost per correct answer for key configs
print()
print(f"{'config':40s} {'acc':>6s} {'$/1k':>8s} {'$ per correct answer':>21s}")
print("-"*80)
for p in sorted(glob.glob("results/*.json")):
    d = json.load(open(p))
    if "accuracy" not in d or not d.get("accuracy") or "rows" not in d: continue
    acc = d["accuracy"]; c = d.get("cost_per_1k_requests_usd") or 0
    if acc and c: print(f"{os.path.basename(p)[:40]:40s} {acc:6.1%} {c:8.4f} {c/1000/acc:21.5f}")
