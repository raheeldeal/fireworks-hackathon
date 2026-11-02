#!/bin/bash
# Full protocol after the test set is locked. Each step appends to ledger.csv; fw.py stops at $3.00.
set -e; cd "$(dirname "$0")/.."; source ~/.zshrc 2>/dev/null
M=accounts/fireworks/models
python3 scripts/gen_data.py --n 400 --out data/all.jsonl --workers 8          # resumes to 400
python3 scripts/split.py                                                       # rebuild train.jsonl (test.jsonl untouched)
python3 ../common/check_leak.py data/test.jsonl data/train.jsonl
# phase 4: baseline sweep
for m in nemotron-lightning-3p5-30b-a3b glm-5p3-flash gpt-oss-120b deepseek-v4p1-flash glm-5p3; do python3 run_eval.py --model $M/$m --prompt prompts/v1_plain.txt; done
python3 run_eval.py --model $M/kimi-k3 --prompt prompts/v1_plain.txt --limit 80
# phase 5: interventions on the small models
for m in glm-5p3-flash nemotron-lightning-3p5-30b-a3b gpt-oss-120b; do
  python3 run_eval.py --model $M/$m --prompt prompts/v2_rubric.txt
  python3 run_eval.py --model $M/$m --prompt prompts/v3_rubric_conf.txt
done
python3 scripts/fewshot.py && python3 run_eval.py --model $M/glm-5p3-flash --prompt prompts/v4_fewshot.txt
python3 run_eval.py --model $M/glm-5p3-flash --prompt prompts/v2_rubric.txt --json-mode
python3 scripts/route.py results/glm-5p3-flash_v3_rubric_conf.json results/glm-5p3_v1_plain.json --thresholds 0.01 0.5 0.7 0.9
# phase 6: variance
scripts/variance.sh $M/glm-5p3-flash prompts/v1_plain.txt
scripts/variance.sh $M/glm-5p3-flash prompts/v2_rubric.txt
python3 scripts/chart.py && python3 compare.py results/*.json
