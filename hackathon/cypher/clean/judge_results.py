"""Judge each exam row by its RESULT: do the rows the answer key returns correctly answer the question?
Two independent judges (Kimi K3, GLM 5.3) see only the question and the returned rows. Never any model attempt."""
import json, os, sys, time, urllib.request, concurrent.futures as cf
KEY=os.environ["FIREWORKS_API_KEY"]
HERE=os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
test=[json.loads(l) for l in open(os.path.join(HERE,"data/test.jsonl"))]
JUDGES=["accounts/fireworks/models/kimi-k3","accounts/fireworks/models/glm-5p3"]
PROMPT="""You are checking an answer key for a database question-answering exam.

Question: {q}

The answer key returns these rows ({n} rows total, up to 25 shown):
{rows}

Do these rows correctly answer the question as asked?
- YES: the rows are exactly what the question asks for. The right entities, the right values, the right number of results.
- NO: the rows answer a different question, return the wrong entities or values, have duplicates or nulls where real answers should be, return a different count than asked, or miss something the question explicitly requests.
- AMBIGUOUS: the question has more than one reasonable correct answer (for example "top 5" when several items are tied at the cutoff, or vague wording).

Reply with exactly one word on the first line (YES, NO or AMBIGUOUS), then one short sentence of reason."""
def ask(model, ex):
    g=ex["gold_result"]; rows=g.get("rows") or []
    body=json.dumps({"model":model,"max_tokens":2048,"temperature":0,
        "messages":[{"role":"user","content":PROMPT.format(q=ex["question"],n=len(rows),rows=json.dumps(rows[:25],ensure_ascii=False)[:4000])}]}).encode()
    for attempt in range(5):
        try:
            req=urllib.request.Request("https://api.fireworks.ai/inference/v1/chat/completions",data=body,
                headers={"Authorization":f"Bearer {KEY}","Content-Type":"application/json"})
            with urllib.request.urlopen(req,timeout=120) as r: d=json.load(r)
            txt=(d["choices"][0]["message"].get("content") or "").strip()
            first=txt.split("\n")[0].strip().upper().strip("*. ")
            v="YES" if first.startswith("YES") else "NO" if first.startswith("NO") else "AMBIGUOUS" if first.startswith("AMBIG") else "UNPARSED"
            return v, txt[:300]
        except Exception as e:
            time.sleep(2*(attempt+1)); err=str(e)
    return "ERROR", err[:200]
out={}
jobs=[(m,ex) for ex in test for m in JUDGES]
with cf.ThreadPoolExecutor(12) as pool:
    for (m,ex),res in zip(jobs,pool.map(lambda j: ask(*j), jobs)):
        out.setdefault(ex["id"],{})[m.split("/")[-1]]=res
json.dump(out,open(os.path.join(HERE,"clean/judgements.json"),"w"),indent=1)
import collections
for m in JUDGES:
    k=m.split("/")[-1]; print(k, collections.Counter(v[k][0] for v in out.values()))
