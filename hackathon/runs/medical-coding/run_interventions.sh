#!/bin/bash
# Phase 5: harness interventions on the two small models, plus the large-model rubric run used as the routing target.
set -e
cd "$(dirname "$0")"
source ~/.zshrc >/dev/null 2>&1
M=accounts/fireworks/models
for P in v2_rubric v3_fewshot v4_rubric_fewshot v5_confidence; do
  python3 run_eval.py --model $M/glm-5p3-flash --prompt prompts/$P.txt --workers 2
  python3 run_eval.py --model $M/nemotron-lightning-3p5-30b-a3b --prompt prompts/$P.txt --extra '{"reasoning_effort":"none"}' --workers 2
done
python3 run_eval.py --model $M/glm-5p3 --prompt prompts/v2_rubric.txt --extra '{"reasoning_effort":"low"}' --workers 2
