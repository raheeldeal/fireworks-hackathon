"""On the clean subset, re-grade answers the strict grader rejected: run the model's query, show its rows and the
verified key's rows to two judges, ask if they give the same answer to the question."""
import json, os, sys, time, urllib.request, concurrent.futures as cf, collections
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from executor import execute
KEY=os.environ["FIREWORKS_API_KEY"]
HERE=os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
clean={json.loads(l)["id"]:json.loads(l) for l in open(os.path.join(HERE,"data/test_clean.jsonl"))}
JUDGES=["accounts/fireworks/models/kimi-k3","accounts/fireworks/models/glm-5p3"]
P="""Question: {q}

Verified correct answer (rows returned by the answer key, up to 20 shown, {gn} total):
{g}

Candidate answer (rows returned by a model's query, up to 20 shown, {pn} total):
{p}

Does the candidate give the same answer to the question as the verified answer? Column names, column order, row order and extra or missing descriptive columns do not matter. What matters: the same entities and the same values for whatever the question actually asks.
Reply with exactly one word on the first line: SAME or DIFFERENT. Then one short reason."""
def ask(model, ex, prows):
    g=ex["gold_result"].get("rows") or []
    body=json.dumps({"model":model,"max_tokens":4096,"temperature":0,"reasoning_effort":"low","messages":[{"role":"user","content":
        P.format(q=ex["question"],gn=len(g),g=json.dumps(g[:20],ensure_ascii=False)[:3500],pn=len(prows),p=json.dumps(prows[:20],ensure_ascii=False)[:3500])}]}).encode()
    for a in range(5):
        try:
            req=urllib.request.Request("https://api.fireworks.ai/inference/v1/chat/completions",data=body,headers={"Authorization":f"Bearer {KEY}","Content-Type":"application/json"})
            with urllib.request.urlopen(req,timeout=120) as r: d=json.load(r)
            t=(d["choices"][0]["message"].get("content") or "").strip(); f=t.split("\n")[0].upper()
            return ("SAME" if "SAME" in f else "DIFFERENT" if "DIFF" in f else "UNPARSED"), t[:200]
        except Exception as e: time.sleep(2*(a+1))
    return "ERROR",""
RUNS={"GLM 5.3 Flash":"glm-5p3-flash_v1_plain_n200.json","Muse 30B + SFT + RFT":"train_rft_r1_reject.json","Muse 30B + SFT":"train_sft.json",
 "Muse 30B base":"train_base.json","harness route":"harness_route_big.json","harness repair":"harness_repair1_rdefault.json",
 "DeepSeek V4.1 Flash":"deepseek-v4p1-flash_v1_plain_n200.json","Kimi K3":"kimi-k3_v1_plain_n100.json",
 "GLM 5.3 large":"glm-5p3_v1_plain_n100.json","Claude Opus 5":"claude-opus-5_v1_plain_n100.json"}
def load(f):
    for d in ("results_v2","results"):
        p=os.path.join(HERE,d,f)
        if os.path.exists(p): return json.load(open(p))
excache={}
def run(g,q):
    k=(g,q)
    if k not in excache: excache[k]=execute(g,q)
    return excache[k]
tasks=[]; per={}
for label,f in RUNS.items():
    d=load(f); rows=[r for r in d["rows"] if r["id"] in clean]; per[label]={"rows":rows,"rescued":set()}
    for r in rows:
        if r["correct"] or not r.get("pred_cypher") or r.get("exec_status") in ("error",): continue
        tasks.append((label,r["id"],r["pred_cypher"]))
print("answers to re-grade:",len(tasks))
def work(t):
    label,rid,q=t; ex=clean[rid]; res=run(ex["graph"],q)
    prows=(res.get("rows") if isinstance(res,dict) else None) or []
    if not prows: return label,rid,("DIFFERENT","empty"),("DIFFERENT","empty")
    return label,rid,ask(JUDGES[0],ex,prows),ask(JUDGES[1],ex,prows)
log=[]
with cf.ThreadPoolExecutor(12) as pool:
    for label,rid,a,b in pool.map(work,tasks):
        log.append({"model":label,"id":rid,"kimi":a,"glm":b})
        if a[0]=="SAME" and b[0]=="SAME": per[label]["rescued"].add(rid)
json.dump(log,open(os.path.join(HERE,"clean/regrade_log.json"),"w"),indent=1)
out={}
print(f"{'model':24s} {'strict':>7s} {'by result':>9s}  n")
for label,v in per.items():
    n=len(v["rows"]); s=sum(r["correct"] for r in v["rows"]); res=s+len(v["rescued"])
    out[label]={"n":n,"strict":s/n,"by_result":res/n,"correct_ids":sorted([r["id"] for r in v["rows"] if r["correct"]]+list(v["rescued"]))}
    print(f"{label:24s} {s/n:7.1%} {res/n:9.1%}  {n}")
json.dump(out,open(os.path.join(HERE,"clean/final_scores.json"),"w"),indent=1)
