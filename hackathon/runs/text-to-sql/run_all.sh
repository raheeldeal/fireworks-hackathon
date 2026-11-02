#!/bin/zsh
# Phases 4-6 end to end. Idempotent: skips a run whose results file already exists.
set -u
cd "$(dirname "$0")"
source ~/.zshrc >/dev/null 2>&1
M=accounts/fireworks/models
run() { # out model prompt [extra args...]
  local out=$1; shift
  if [[ -f results/$out.json ]]; then echo "skip $out"; return; fi
  python3 run_eval.py "$@" --out results/$out.json 2>&1 | tail -3
}
echo "== phase 4: baselines  $(date)"
run nemotron-lightning-3p5-30b-a3b_v1_plain --model $M/nemotron-lightning-3p5-30b-a3b --prompt prompts/v1_plain.txt --workers 6
run glm-5p3-flash_v1_plain --model $M/glm-5p3-flash --prompt prompts/v1_plain.txt --workers 6
run gpt-oss-120b_v1_plain --model $M/gpt-oss-120b --prompt prompts/v1_plain.txt --workers 6 --extra '{"reasoning_effort":"low"}'
run deepseek-v4p1-flash_v1_plain --model $M/deepseek-v4p1-flash --prompt prompts/v1_plain.txt --workers 6
run glm-5p3_v1_plain --model $M/glm-5p3 --prompt prompts/v1_plain.txt --workers 4 --extra '{"reasoning_effort":"low"}'
run kimi-k3_v1_plain --model $M/kimi-k3 --prompt prompts/v1_plain.txt --workers 4 --limit 100
python3 compare.py
echo "== phase 5: prompt interventions on the two small models  $(date)"
for s in nemotron-lightning-3p5-30b-a3b glm-5p3-flash; do
  run ${s}_v2_rubric --model $M/$s --prompt prompts/v2_rubric.txt --workers 6
  run ${s}_v3_fewshot --model $M/$s --prompt prompts/v3_fewshot.txt --workers 6
done
run glm-5p3-flash_v2_rubric_json --model $M/glm-5p3-flash --prompt prompts/v2_rubric_json.txt --workers 6 --extra '{"response_format":{"type":"json_object"}}'
python3 compare.py
echo "== done $(date)"
