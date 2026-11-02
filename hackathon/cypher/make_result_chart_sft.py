#!/usr/bin/env python3
"""The 'strong result' chart: horizontal bars sorted, baseline hatched, delta vs baseline in pp
with a paired bootstrap test on the SAME rows (per-row correctness), n.s. if 95% CI crosses 0."""
import json, os, glob, random, matplotlib
matplotlib.use("Agg"); import matplotlib.pyplot as plt
random.seed(7)
def load(f):
    for d in ("results_v2","results"):
        p=f"{d}/{f}"
        if os.path.exists(p): return json.load(open(p))
RUNS=[("Muse Glimmer 30B (baseline, before SFT)","train_base.json",True),
      ("Muse Glimmer 30B + LoRA SFT + RFT","train_rft_r1_reject.json",False),
      ("Muse Glimmer 30B + LoRA SFT","train_sft.json",False),
      ("GLM Flash + harness (route to GLM 5.3)","harness_route_big.json",False),
      ("GLM Flash + harness (repair once)","harness_repair1_rdefault.json",False),
      ("GLM Flash + harness (vote of 3)","harness_vote3.json",False),
      ("DeepSeek V4.1 Flash","deepseek-v4p1-flash_v1_plain_n200.json",False),
      ("Kimi K3 (100 q)","kimi-k3_v1_plain_n100.json",False),
      ("GLM 5.3 large (100 q)","glm-5p3_v1_plain_n100.json",False),("Claude Opus 5, closed (100 q)","claude-opus-5_v1_plain_n100.json",False)]
for extra in []:
    d=json.load(open(extra))
    if d.get("accuracy"): RUNS.append((d["model"]+" (100 q)",os.path.basename(extra),False))
base=load(RUNS[0][1]); bmap={r["id"]:bool(r["correct"]) for r in base["rows"]}
bars=[]
for label,f,isb in RUNS:
    d=load(f)
    if not d: continue
    rows={r["id"]:bool(r["correct"]) for r in d["rows"]}
    ids=[i for i in rows if i in bmap]
    acc=sum(rows[i] for i in ids)/len(ids); bacc=sum(bmap[i] for i in ids)/len(ids)
    diffs=[rows[i]-bmap[i] for i in ids]
    boots=[]
    for _ in range(2000):
        s=[diffs[random.randrange(len(diffs))] for _ in diffs]; boots.append(sum(s)/len(s))
    boots.sort(); lo,hi=boots[int(.025*len(boots))],boots[int(.975*len(boots))]
    sig = not (lo<=0<=hi)
    bars.append((label,acc*100,(acc-bacc)*100,sig,isb,len(ids)))
bars.sort(key=lambda b:b[1])
fig,ax=plt.subplots(figsize=(11,0.55*len(bars)+2.2),dpi=150)
for i,(label,acc,delta,sig,isb,n) in enumerate(bars):
    ax.barh(i,acc,color="#444" if isb else ("#d9480f" if delta>0 and sig else "#8a8a8a" if not sig else "#b5651d"),
            hatch="///" if isb else None,edgecolor="black" if isb else "none",height=.62)
    ax.text(acc+0.8,i,f"{acc:.1f}%",va="center",fontsize=9)
    if not isb:
        ax.text(101,i,f"{delta:+.1f}pp  {'significant' if sig else 'n.s.'}",va="center",fontsize=9,
                color="#1f5f4e" if (sig and delta>0) else ("#8a1c1c" if (sig and delta<0) else "#777"))
ax.set_yticks(range(len(bars))); ax.set_yticklabels([b[0] for b in bars],fontsize=9)
ax.set_xlim(0,100); ax.set_xlabel("execution accuracy on the locked text-to-Cypher test set (%)")
ax.set_title("Before → after: does fine-tuning or the harness beat the baseline?\n200 questions, 5 live Neo4j graphs; Δ vs Muse Glimmer 30B base, paired bootstrap 95% CI on the same questions",
             fontsize=11,loc="left")
ax.grid(axis="x",alpha=.3); ax.set_axisbelow(True)
for s in ("top","right"): ax.spines[s].set_visible(False)
plt.tight_layout(); plt.savefig("result_chart_sft.png",bbox_inches="tight"); print("result_chart_sft.png")
for b in bars: print(f"{b[0]:40s} {b[1]:5.1f}%  {b[2]:+5.1f}pp  {'sig' if b[3] else 'n.s.'}  n={b[5]}")
