#!/usr/bin/env bash
# Full CypherBench ladder with this repo's harness and scorer. Run from hackathon/cypher with FIREWORKS_API_KEY set
# (adapter configs need the key of the account that owns the LoRA). Graphs: cypherbench/docker -> docker compose up -d
set -u
D="--data cypherbench/test.jsonl --no-trace"
H="--shots 3 --fix --repair 3 --escalate kimi-k3"
run() { python cypherbench/run_cb.py "$@" $D > "results/$2.log" 2>&1; tail -2 "results/$2.log"; }
# baselines: plain single call, no harness
run --tag cb_r1_base --model muse-glimmer-30b --workers 6 &
run --tag cb_glm-5p3-flash --model glm-5p3-flash --workers 4 &
run --tag cb_deepseek-v4p1-flash --model deepseek-v4p1-flash --workers 4 &
run --tag cb_kimi-k3 --model kimi-k3 --workers 4 &
# harness on base, then SFT adapters inside the same harness
run --tag cb_r5_full --model muse-glimmer-30b $H --workers 6 &
run --tag cb_r6_ft1 --model-path vishwajeethogale/run-01ffc6feb14c4e0d8f17fa876503b258/ft1-52823-fc84ed85 $H --workers 6 &
run --tag cb_r6bx_ftbx --model-path vishwajeethogale/run-e9231841f99744a3a291562a0e98cf30/ftbx-56948-f3cd2ac9 $H --workers 6 &
wait
