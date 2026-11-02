#!/usr/bin/env bash
# Managed LoRA SFT on the smallest useful tunable base under 16B (qwen3-4b-instruct-2507, $0.50/M training tokens).
# RESULT CANNOT BE SCORED TONIGHT: no tunable base under 16B supports serverless LoRA serving (firectl model get ->
# "Supports Serverless Lora: false"), and the managed-SFT doc says an on-demand (dedicated) deployment is the only
# way to serve it. Protocol rule 3 forbids dedicated deployments, so the row is "not scored (dedicated deployment
# required)". These are the exact commands; the deployment ones are commented out on purpose.
set -euo pipefail
cd "$(dirname "$0")"
source ~/.zshrc 2>/dev/null || true
: "${FIREWORKS_API_KEY:?set FIREWORKS_API_KEY}"
ACCT=raheeldeal
DS=regex-sft-v1
BASE=accounts/fireworks/models/qwen3-4b-instruct-2507
OUT=regex-qwen3-4b-lora

venv/bin/python make_sft.py                                    # -> data/sft_train.jsonl
venv/bin/python ../common/check_leak.py data/test.jsonl data/sft_train.jsonl
firectl dataset create "$DS" data/sft_train.jsonl --api-key "$FIREWORKS_API_KEY" -a "$ACCT"
firectl sftj create --base-model "$BASE" --dataset "$DS" --output-model "$OUT" --lora-rank 8 --epochs 2 \
  --api-key "$FIREWORKS_API_KEY" -a "$ACCT"                   # prints the job id; ~$0.05 for ~100k tokens
# poll:   firectl sftj get <JOB_ID> -a $ACCT --api-key $FIREWORKS_API_KEY
# model:  firectl model get accounts/$ACCT/models/$OUT

# --- NOT RUN (protocol rule 3: no dedicated / on-demand deployments) ---
# firectl deployment create accounts/$ACCT/models/$OUT --deployment-shape default --min-replica-count 1 --max-replica-count 1 --preemptible
# venv/bin/python run_eval.py --model accounts/$ACCT/models/$OUT --prompt prompts/v1_plain.txt
# firectl deployment delete <DEPLOYMENT_ID>
