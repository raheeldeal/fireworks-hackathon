#!/bin/zsh
# Phase 4: plain prompt, all six models, default reasoning, seed 0 (file order). kimi-k3 capped at 100 rows.
source ~/.zshrc >/dev/null 2>&1
cd "$(dirname "$0")"
P=prompts/v1_plain.txt
python3 run_eval.py --model nemotron-lightning-3p5-30b-a3b --prompt $P --workers 4 --logprobs > results/log_nemotron_plain.txt 2>&1 &
python3 run_eval.py --model glm-5p3-flash --prompt $P --workers 4 --logprobs > results/log_glmflash_plain.txt 2>&1 &
wait
python3 run_eval.py --model gpt-oss-120b --prompt $P --workers 4 --logprobs > results/log_gptoss_plain.txt 2>&1 &
python3 run_eval.py --model deepseek-v4p1-flash --prompt $P --workers 4 --logprobs > results/log_deepseek_plain.txt 2>&1 &
wait
python3 run_eval.py --model glm-5p3 --prompt $P --workers 4 > results/log_glm_plain.txt 2>&1 &
python3 run_eval.py --model kimi-k3 --prompt $P --workers 3 --limit 100 > results/log_kimi_plain.txt 2>&1 &
wait
echo BASELINES DONE
