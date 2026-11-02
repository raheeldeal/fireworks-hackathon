# Deploying the catalog-free LoRA (for a teammate with credits)

Nothing here was run on the hackathon account (no credits, rule: never create a dedicated deployment). Every command was
checked against `firectl 1.8.22 --help` and docs.fireworks.ai on 2026-11-02. Budget: one H200 for about 1 hour.

**Which model.** The best LoRA is promoted to an account model, so it survives session deletion. The id is in
`results/BEST_MODEL.txt` (format `accounts/raheeldeal/models/<id>`). Fireworks serves trained LoRAs only on on-demand
(dedicated) deployments; there is no serverless per-token path for our own LoRA.

## 0. Auth

```bash
export FIREWORKS_API_KEY=...        # the account that owns the promoted model (raheeldeal) or an account it was shared with
firectl set-api-key "$FIREWORKS_API_KEY"   # or pass --api-key on every command
export MODEL=$(cat results/BEST_MODEL.txt)  # e.g. accounts/raheeldeal/models/tool-router-sft
```

## 1. Create the deployment (base model + addons), load the LoRA

```bash
# BF16 H200 shape for muse-glimmer-30b (from `firectl deployment-shape-version list --base-model accounts/fireworks/models/muse-glimmer-30b`)
firectl deployment create accounts/fireworks/models/muse-glimmer-30b \
  --deployment-shape accounts/fireworks/deploymentShapes/dkuwotf7 \
  --enable-addons --min-replica-count 1 --max-replica-count 1 \
  --display-name tool-router-demo --wait
# note the deployment id it prints, e.g. accounts/raheeldeal/deployments/abc123
export DEP=accounts/raheeldeal/deployments/<id>

firectl load-lora "$MODEL" --deployment "$DEP" --wait
firectl deployed-model list --deployment "$DEP"      # state must be DEPLOYED
```

The model id to call is `$MODEL#$DEP`.

## 2. Call it with the bare request (no catalog)

```bash
curl -s https://api.fireworks.ai/inference/v1/chat/completions \
  -H "Authorization: Bearer $FIREWORKS_API_KEY" -H "Content-Type: application/json" \
  -d "{\"model\": \"$MODEL#$DEP\", \"max_tokens\": 16, \"temperature\": 0,
       \"messages\": [{\"role\": \"system\", \"content\": \"Reply with the single best tool name.\"},
                      {\"role\": \"user\", \"content\": \"Push PAY-77, PAY-78 and PAY-81 into the Q3 hardening sprint that starts Monday.\"}]}" \
  | python3 -c 'import json,sys; d=json.load(sys.stdin); print(d["choices"][0]["message"]["content"], d["usage"])'
# expected: jira.move_to_sprint   prompt_tokens ~70, completion_tokens ~6
```

## 3. Measure p50 over 50 calls (and accuracy on those rows)

```bash
python3 bench.py --model "$MODEL#$DEP" --bare --n 50          # -> results/bench_tuned_bare.json
python3 bench.py --model accounts/fireworks/models/glm-5p3-flash --catalog --n 50   # stock comparison, same 50 rows
```

`bench.py` prints accuracy, p50/p95 latency and mean prompt/completion tokens per call; both JSONs have per-row records.

## 4. Tear down (do this before leaving the venue)

```bash
firectl unload-lora "$MODEL" --deployment "$DEP"
firectl deployment delete "$DEP" --wait
firectl deployment list                                    # must show nothing running
```

## Demo: two side-by-side curls

Left terminal, stock small model with the 1,560-token catalog prompt (`prompts/v1_plain.txt` + `data/catalog.txt`):

```bash
SYS=$(python3 -c 'import json; p=open("../prompts/v1_plain.txt").read().replace("{CATALOG}", open("../data/catalog.txt").read().strip()); print(json.dumps(p))')
REQ='"Push PAY-77, PAY-78 and PAY-81 into the Q3 hardening sprint that starts Monday."'
time curl -s https://api.fireworks.ai/inference/v1/chat/completions \
  -H "Authorization: Bearer $FIREWORKS_API_KEY" -H "Content-Type: application/json" \
  -d "{\"model\": \"accounts/fireworks/models/glm-5p3-flash\", \"max_tokens\": 32, \"temperature\": 0, \"reasoning_effort\": \"low\",
       \"messages\": [{\"role\": \"system\", \"content\": $SYS}, {\"role\": \"user\", \"content\": $REQ}]}" \
  | python3 -c 'import json,sys; d=json.load(sys.stdin); print(d["choices"][0]["message"]["content"].strip(), "| tokens:", d["usage"]["prompt_tokens"], "in", d["usage"]["completion_tokens"], "out")'
```

Right terminal, tuned model with the bare request:

```bash
time curl -s https://api.fireworks.ai/inference/v1/chat/completions \
  -H "Authorization: Bearer $FIREWORKS_API_KEY" -H "Content-Type: application/json" \
  -d "{\"model\": \"$MODEL#$DEP\", \"max_tokens\": 16, \"temperature\": 0,
       \"messages\": [{\"role\": \"system\", \"content\": \"Reply with the single best tool name.\"}, {\"role\": \"user\", \"content\": $REQ}]}" \
  | python3 -c 'import json,sys; d=json.load(sys.stdin); print(d["choices"][0]["message"]["content"].strip(), "| tokens:", d["usage"]["prompt_tokens"], "in", d["usage"]["completion_tokens"], "out")'
```

Same answer, roughly 1,700 vs 70 prompt tokens. Cost per call printed from `usage` × the price table in `PROTOCOL.md`.

## If the promoted model is missing

The sampler checkpoint only lives inside the training session, and sessions were deleted to free the slot. Re-train
(free, about 40 steps) and promote before deleting:

```bash
PY=../../runs/regex/venv311/bin/python
$PY tune.py train --data ../data/train.jsonl --tag sft           # or --data data/rft_round1.jsonl --tag rft1
$PY tune.py promote --session results/sft_session.json --model-id tool-router-sft
$PY tune.py cleanup --session results/sft_session.json
```
