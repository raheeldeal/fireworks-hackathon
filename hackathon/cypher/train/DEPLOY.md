# Deploying the text-to-Cypher LoRA (for a teammate with credits)

Nothing here was run on the hackathon account (rule: never create a dedicated deployment). Commands follow the sibling
`hackathon/submission/train/DEPLOY.md`, which was checked against `firectl 1.8.22 --help` and docs.fireworks.ai on 2026-11-02.
Fireworks serves our own LoRAs only on on-demand (dedicated) deployments; the serverless sampler we scored with is a
training-pool endpoint, not a production API. Budget: one H200 for about 1 hour.

**Which model.** Every trained round was promoted to an account model so it survives session deletion. The ids are in
`train/results/<tag>_session.json` under `promoted_model`; the best one is named in `TRAIN.md`
(for example `accounts/raheeldeal/models/cypher-sft-1150`).

## 0. Auth

```bash
export FIREWORKS_API_KEY=...          # account raheeldeal, or an account the model was shared with
firectl set-api-key "$FIREWORKS_API_KEY"
export MODEL=accounts/raheeldeal/models/<best id from TRAIN.md>
```

## 1. Create the deployment and load the LoRA

```bash
# BF16 H200 shape for muse-glimmer-30b (`firectl deployment-shape-version list --base-model accounts/fireworks/models/muse-glimmer-30b`)
firectl deployment create accounts/fireworks/models/muse-glimmer-30b \
  --deployment-shape accounts/fireworks/deploymentShapes/dkuwotf7 \
  --enable-addons --min-replica-count 1 --max-replica-count 1 \
  --display-name cypher-lora-demo --wait
export DEP=accounts/raheeldeal/deployments/<id printed above>

firectl load-lora "$MODEL" --deployment "$DEP" --wait
firectl deployed-model list --deployment "$DEP"        # state must be DEPLOYED
```

The model id to call is `$MODEL#$DEP`.

## 2. Call it with the same prompt we trained and scored with

System message = `prompts/v1_plain.txt` with `{schema}` replaced by the graph schema text from the dataset row; user
message = the question. Temperature 0. Muse Glimmer has a reasoning channel; we scored with reasoning off, so pass
`reasoning_effort: "low"` (if the deployment rejects it, drop it; the tuned model was trained to answer directly).

```bash
cd hackathon/cypher
python3 - <<'EOF'
import json, os, urllib.request
row = json.loads(open("data/test.jsonl").readline())
system = open("prompts/v1_plain.txt").read().replace("{schema}", row["schema"])
body = {"model": os.environ["MODEL"] + "#" + os.environ["DEP"], "temperature": 0, "max_tokens": 400,
        "reasoning_effort": "low",
        "messages": [{"role": "system", "content": system}, {"role": "user", "content": row["question"]}]}
req = urllib.request.Request("https://api.fireworks.ai/inference/v1/chat/completions", data=json.dumps(body).encode(),
      headers={"Authorization": "Bearer " + os.environ["FIREWORKS_API_KEY"], "Content-Type": "application/json"})
out = json.load(urllib.request.urlopen(req))
print(row["question"]); print(out["choices"][0]["message"]["content"]); print(out["usage"])
EOF
```

## 3. Re-score the full locked set through the deployment

`run_eval.py` takes any model id; add the id to its `PRICING` dict first (cost is GPU-hours, so put `(0.0, 0.0)` and
report the deployment's hourly price separately):

```bash
.venv/bin/python run_eval.py --model "$MODEL#$DEP" --extra '{"reasoning_effort":"low"}' --max-tokens 400 \
  --out results/train_deployed.json
```

Expect accuracy within a couple of points of `results/train_<best>.json` (same weights; the chat-completions template may
differ slightly from our token-level prefill).

## 4. Tear down before leaving

```bash
firectl unload-lora "$MODEL" --deployment "$DEP"
firectl deployment delete "$DEP" --wait
firectl deployment list                                   # must show nothing running
```

## If the promoted model is missing

Re-train (free, ~10 minutes for SFT) and the script promotes automatically before deleting the session:

```bash
cd hackathon/cypher
PYTHONPATH=train/.pylib ../runs/regex/venv311/bin/python train/rl.py train --data data/train.jsonl --tag sft --epochs 2 --rank 16
```
