#!/bin/bash
cd "$(dirname "$0")/.."; source ~/.zshrc 2>/dev/null; M=accounts/fireworks/models
for m in nemotron-lightning-3p5-30b-a3b glm-5p3-flash gpt-oss-120b deepseek-v4p1-flash glm-5p3; do python3 run_eval.py --model $M/$m --prompt prompts/v1_plain.txt --workers 6 2>&1 | grep -v "^ERR" ; done
python3 run_eval.py --model $M/kimi-k3 --prompt prompts/v1_plain.txt --limit 70 --workers 4 2>&1 | grep -v "^ERR"
echo SWEEP DONE
