#!/bin/bash
# Phase 5c: harness levers + 3 seeds on nemotron with reasoning disabled (reasoning_effort none)
set -u
cd "$(dirname "$0")"
N=nemotron-lightning-3p5-30b-a3b
R=(--model accounts/fireworks/models/$N --max-tokens 1024 --reasoning-effort none --logprobs)
run() { local stem=$1; shift; [ -f "results/$stem.json" ] && { echo "skip $stem"; return; }; python3 run_eval.py --name "$stem" "$@" 2>&1 | grep -E "strict|rror" | tail -2; }
run ${N}_tools_v2_rubric_renone        "${R[@]}" --mode tools --prompt prompts/v2_rubric.txt
run ${N}_json_v1_plain_renone          "${R[@]}" --mode json  --prompt prompts/v1_plain.txt
run ${N}_tools_v1_plain_required_renone "${R[@]}" --mode tools --prompt prompts/v1_plain.txt --tool-choice required
for s in 1 2 3; do run ${N}_tools_v1_plain_renone_seed$s "${R[@]}" --mode tools --prompt prompts/v1_plain.txt --seed $s; done
# best config (required + no reasoning): 3 seeds
for s in 1 2 3; do run ${N}_tools_v1_plain_required_renone_seed$s "${R[@]}" --mode tools --prompt prompts/v1_plain.txt --tool-choice required --seed $s; done
