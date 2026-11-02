import json, os, sys, time, urllib.request, urllib.error
key=os.environ["FIREWORKS_API_KEY"]
sysp=open("prompts/v2_conf.txt").read()
text="Where do I find the virtual card?"
def call(model, extra, max_tokens=2048):
    p={"model":model,"max_tokens":max_tokens,"temperature":0,"messages":[{"role":"system","content":sysp},{"role":"user","content":text}]}
    p.update(extra)
    req=urllib.request.Request("https://api.fireworks.ai/inference/v1/chat/completions",data=json.dumps(p).encode(),headers={"Authorization":f"Bearer {key}","Content-Type":"application/json"})
    t0=time.time()
    try:
        with urllib.request.urlopen(req,timeout=120) as r: d=json.load(r)
    except urllib.error.HTTPError as e:
        return f"HTTP {e.code}: {e.read()[:300]}"
    u=d.get("usage",{}); m=d["choices"][0]["message"]
    rt=(u.get("completion_tokens_details") or {}).get("reasoning_tokens")
    return f"{time.time()-t0:.1f}s out={u.get('completion_tokens')} reas={rt} fin={d['choices'][0].get('finish_reason')} content={repr((m.get('content') or '')[:80])} has_reasoning_field={'reasoning_content' in m or 'reasoning' in m}"
model=sys.argv[1]
for name,extra in [("plain",{}),("effort_none",{"reasoning_effort":"none"}),("effort_low",{"reasoning_effort":"low"}),("thinking_disabled",{"thinking":{"type":"disabled"}})]:
    print(model.split('/')[-1], name, "->", call(model, extra))
