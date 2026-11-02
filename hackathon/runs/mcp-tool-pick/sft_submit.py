#!/usr/bin/env python3
"""Managed LoRA SFT on Muse Glimmer 30B (free until 2026-11-30 per docs) via the REST API. Stdlib only.
  python3 sft_submit.py submit   -> creates dataset, uploads data/train_sft.jsonl, creates job; writes results/sft_job.json
  python3 sft_submit.py poll     -> polls the job until a terminal state; appends states to results/sft_job.json
"""
import json, os, sys, time, urllib.request, urllib.error, uuid
KEY = os.environ["FIREWORKS_API_KEY"]; ACCOUNT = os.environ.get("FW_ACCOUNT", "raheeldeal")
BASE = f"https://api.fireworks.ai/v1/accounts/{ACCOUNT}"
BASE_MODEL = "accounts/fireworks/models/muse-glimmer-30b"
STATE = "results/sft_job.json"

def call(method, url, body=None, headers=None, raw=None):
    h = {"Authorization": f"Bearer {KEY}"}; h.update(headers or {})
    data = raw if raw is not None else (json.dumps(body).encode() if body is not None else None)
    if body is not None: h["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=data, method=method, headers=h)
    try:
        with urllib.request.urlopen(req, timeout=120) as r:
            return r.status, json.loads(r.read() or b"{}")
    except urllib.error.HTTPError as e:
        return e.code, {"error": e.read().decode(errors="replace")[:500]}

def submit():
    run = time.strftime("%Y%m%d-%H%M%S"); ds_id = f"mcp-tool-pick-{run}"; model_id = f"mcp-tool-pick-muse-{run}"
    rows = sum(1 for l in open("data/train_sft.jsonl") if l.strip())
    st, r = call("POST", f"{BASE}/datasets", {"datasetId": ds_id, "dataset": {"userUploaded": {}, "exampleCount": str(rows)}})
    print("create dataset", st, json.dumps(r)[:200])
    if st != 200: sys.exit(1)
    boundary = uuid.uuid4().hex; fb = open("data/train_sft.jsonl", "rb").read()
    body = (f"--{boundary}\r\nContent-Disposition: form-data; name=\"file\"; filename=\"train_sft.jsonl\"\r\nContent-Type: application/jsonl\r\n\r\n").encode() + fb + f"\r\n--{boundary}--\r\n".encode()
    st, r = call("POST", f"{BASE}/datasets/{ds_id}:upload", raw=body, headers={"Content-Type": f"multipart/form-data; boundary={boundary}"})
    print("upload", st, json.dumps(r)[:200])
    if st != 200: sys.exit(1)
    for _ in range(30):  # wait for dataset READY
        st, r = call("GET", f"{BASE}/datasets/{ds_id}"); s = r.get("state"); print("dataset state", s)
        if s == "READY": break
        time.sleep(5)
    job = {"supervisedFineTuningJob": {"baseModel": BASE_MODEL, "dataset": f"accounts/{ACCOUNT}/datasets/{ds_id}",
           "outputModel": f"accounts/{ACCOUNT}/models/{model_id}", "loraRank": 8, "epochs": 2,
           "displayName": "mcp-tool-pick catalog-free router"}}
    st, r = call("POST", f"{BASE}/supervisedFineTuningJobs", job)
    print("create job", st, json.dumps(r)[:400])
    if st != 200: sys.exit(1)
    json.dump({"dataset": ds_id, "output_model": job["supervisedFineTuningJob"]["outputModel"], "job": r,
               "job_name": r.get("name"), "states": []}, open(STATE, "w"), indent=1)

def poll():
    s = json.load(open(STATE)); name = s["job_name"]
    terminal = ("JOB_STATE_COMPLETED", "JOB_STATE_FAILED", "JOB_STATE_CANCELLED", "COMPLETED", "FAILED", "CANCELLED")
    for _ in range(240):  # up to 4 hours
        st, r = call("GET", f"https://api.fireworks.ai/v1/{name}")
        state = r.get("state"); msg = (r.get("status") or {}).get("message", "")
        s["states"].append({"t": time.strftime("%H:%M:%S"), "state": state, "msg": msg}); s["last"] = r
        json.dump(s, open(STATE, "w"), indent=1); print(time.strftime("%H:%M:%S"), st, state, str(msg)[:100], flush=True)
        if state in terminal or (st != 200 and st != 429): break
        time.sleep(60)

{"submit": submit, "poll": poll}[sys.argv[1]]()
