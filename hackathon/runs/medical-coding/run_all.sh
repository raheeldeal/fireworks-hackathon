#!/bin/bash
# Every paid row, in protocol order. Stops on the $3 cap (fw.py raises CapReached).
set -e
cd "$(dirname "$0")"
source ~/.zshrc >/dev/null 2>&1
M=accounts/fireworks/models
# Phase 4: baselines, plain prompt, seed 7. glm-5p3 uses reasoning_effort=low (thinking-only model; see DECISIONS.md).
python3 run_eval.py --model $M/nemotron-lightning-3p5-30b-a3b --prompt prompts/v1_plain.txt
python3 run_eval.py --model $M/glm-5p3-flash --prompt prompts/v1_plain.txt
python3 run_eval.py --model $M/gpt-oss-120b --prompt prompts/v1_plain.txt
python3 run_eval.py --model $M/deepseek-v4p1-flash --prompt prompts/v1_plain.txt
python3 run_eval.py --model $M/glm-5p3 --prompt prompts/v1_plain.txt --extra '{"reasoning_effort":"low"}'
