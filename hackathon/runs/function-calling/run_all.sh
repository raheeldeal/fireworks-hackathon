#!/bin/bash
# Full reproducible pipeline (phases 4-6, 8). Each step appends to ledger.csv; run_eval.py refuses to start past the $3 cap.
# Usage: ./run_all.sh            (skips steps whose results file already exists)
set -u
cd "$(dirname "$0")"
source ~/.zshrc >/dev/null 2>&1
M=accounts/fireworks/models
run() {  # run <results stem> <args...>
  local stem=$1; shift
  if [ -f "results/$stem.json" ]; then echo "skip $stem (exists)"; return; fi
  python3 run_eval.py --name "$stem" "$@" 2>&1 | tail -3
}

echo "=== Phase 4: baseline sweep (tools mode + json mode), plain prompt ==="
run nemotron-lightning-3p5-30b-a3b_tools_v1_plain --model $M/nemotron-lightning-3p5-30b-a3b --mode tools --logprobs
run nemotron-lightning-3p5-30b-a3b_json_v1_plain  --model $M/nemotron-lightning-3p5-30b-a3b --mode json  --logprobs
run glm-5p3-flash_tools_v1_plain --model $M/glm-5p3-flash --mode tools --logprobs
run glm-5p3-flash_json_v1_plain  --model $M/glm-5p3-flash --mode json  --logprobs
run gpt-oss-120b_tools_v1_plain  --model $M/gpt-oss-120b --mode tools
run gpt-oss-120b_json_v1_plain   --model $M/gpt-oss-120b --mode json
run deepseek-v4p1-flash_tools_v1_plain --model $M/deepseek-v4p1-flash --mode tools
run deepseek-v4p1-flash_json_v1_plain  --model $M/deepseek-v4p1-flash --mode json
run glm-5p3_tools_v1_plain_relow --model $M/glm-5p3 --mode tools --reasoning-effort low
run glm-5p3_json_v1_plain_relow  --model $M/glm-5p3 --mode json  --reasoning-effort low --limit 100
run kimi-k3_tools_v1_plain --model $M/kimi-k3 --mode tools --limit 100 --concurrency 2

echo "=== Phase 5: harness interventions on the best small model (nemotron unless overridden) ==="
SMALL=${SMALL:-nemotron-lightning-3p5-30b-a3b}
run ${SMALL}_tools_v2_rubric        --model $M/$SMALL --mode tools --prompt prompts/v2_rubric.txt --logprobs
run ${SMALL}_json_v2_rubric         --model $M/$SMALL --mode json  --prompt prompts/v2_rubric.txt --logprobs
run ${SMALL}_json_v2_rubric_shots5  --model $M/$SMALL --mode json  --prompt prompts/v2_rubric.txt --shots 5 --logprobs
run ${SMALL}_tools_v2_rubric_required --model $M/$SMALL --mode tools --prompt prompts/v2_rubric.txt --tool-choice required --logprobs
run ${SMALL}_json_v2_rubric_json_schema --model $M/$SMALL --mode json --prompt prompts/v2_rubric.txt --response-format json_schema --logprobs
# routing: offline from per-row results (DECISIONS.md #7). Big = glm-5p3 tools (reasoning low).
python3 route.py results/${SMALL}_tools_v1_plain.json results/glm-5p3_tools_v1_plain_relow.json | tail -14

echo "=== Phase 6: variance, 3 seeds (shuffled order) for baseline and best small config ==="
for s in 1 2 3; do
  run ${SMALL}_tools_v1_plain_seed$s --model $M/$SMALL --mode tools --seed $s --logprobs
done
BEST_ARGS=${BEST_ARGS:-"--mode tools --prompt prompts/v2_rubric.txt"}
BEST_STEM=${BEST_STEM:-${SMALL}_tools_v2_rubric}
for s in 1 2 3; do
  run ${BEST_STEM}_seed$s --model $M/$SMALL $BEST_ARGS --seed $s --logprobs
done

echo "=== Phase 5b: nemotron reruns with a 4096-token output budget (decision 11: 1024 truncated its reasoning) ==="
N=$M/nemotron-lightning-3p5-30b-a3b
run nemotron-lightning-3p5-30b-a3b_tools_v1_plain_mt4096        --model $N --mode tools --max-tokens 4096 --logprobs
run nemotron-lightning-3p5-30b-a3b_json_v1_plain_mt4096         --model $N --mode json  --max-tokens 4096
run nemotron-lightning-3p5-30b-a3b_tools_v2_rubric_mt4096       --model $N --mode tools --max-tokens 4096 --logprobs --prompt prompts/v2_rubric.txt
run nemotron-lightning-3p5-30b-a3b_tools_v3_misses_mt4096       --model $N --mode tools --max-tokens 4096 --logprobs --prompt prompts/v3_misses.txt
run nemotron-lightning-3p5-30b-a3b_tools_v1_plain_mt4096_relow  --model $N --mode tools --max-tokens 4096 --logprobs --reasoning-effort low
for s in 1 2 3; do run nemotron-lightning-3p5-30b-a3b_json_v1_plain_mt4096_seed$s --model $N --mode json --max-tokens 4096 --seed $s; done
run nemotron-lightning-3p5-30b-a3b_tools_v1_plain_renone        --model $N --mode tools --max-tokens 1024 --logprobs --reasoning-effort none
bash run_renone.sh
python3 route.py results/nemotron-lightning-3p5-30b-a3b_tools_v1_plain_renone.json results/glm-5p3-flash_tools_v1_plain.json | tail -3
python3 fix_cost.py
python3 route.py results/nemotron-lightning-3p5-30b-a3b_tools_v1_plain_mt4096.json results/glm-5p3-flash_tools_v1_plain.json | tail -3
python3 route.py results/glm-5p3-flash_tools_v1_plain.json results/glm-5p3_tools_v1_plain_relow.json | tail -3

echo "=== Phase 8: chart ==="
python3 frontier.py
python3 compare.py
