#!/bin/zsh
# Runs every remaining paid phase in order once the account is unblocked. Safe to re-run: retry mode skips answered rows.
set -u
cd "$(dirname "$0")"; source ~/.zshrc >/dev/null 2>&1
M=accounts/fireworks/models
N=$M/nemotron-lightning-3p5-30b-a3b; G=$M/glm-5p3-flash; O=$M/gpt-oss-120b; D=$M/deepseek-v4p1-flash; L=$M/glm-5p3; K=$M/kimi-k3
log() { echo "[$(date +%H:%M:%S)] $*"; }

log "phase 4: complete baselines (errored rows only)"
python3 run_eval.py --model $N --prompt prompts/v1_plain.txt --workers 3 --retry-errors results/nemotron-lightning-3p5-30b-a3b_v1_plain.json &
python3 run_eval.py --model $D --prompt prompts/v1_plain.txt --workers 3 --retry-errors results/deepseek-v4p1-flash_v1_plain.json &
python3 run_eval.py --model $L --prompt prompts/v1_plain.txt --workers 3 --retry-errors results/glm-5p3_v1_plain.json &
python3 run_eval.py --model $K --prompt prompts/v1_plain.txt --limit 100 --workers 2 --retry-errors results/kimi-k3_v1_plain_n100.json &
wait

log "phase 5a: confidence prompt, thinking vs no-think, both small models"
python3 run_eval.py --model $N --prompt prompts/v2_conf.txt --workers 3 &
python3 run_eval.py --model $N --prompt prompts/v2_conf.txt --effort none --workers 3 &
python3 run_eval.py --model $G --prompt prompts/v2_conf.txt --workers 3 &
python3 run_eval.py --model $G --prompt prompts/v2_conf.txt --effort low --workers 3 &
wait

log "phase 5b: rubric, few-shot, JSON schema mode (small models, cheapest reasoning setting)"
python3 run_eval.py --model $G --prompt prompts/v3_rubric.txt --effort low --workers 3 &
python3 run_eval.py --model $G --prompt prompts/v4_fewshot.txt --effort low --workers 3 &
python3 run_eval.py --model $G --prompt prompts/v3_rubric.txt --effort low --json-mode --workers 3 &
python3 run_eval.py --model $N --prompt prompts/v3_rubric.txt --effort none --workers 3 &
python3 run_eval.py --model $N --prompt prompts/v3_rubric.txt --effort none --json-mode --workers 3 &
wait

log "phase 5c: gpt-oss with confidence prompt (medium-cost escalation target)"
python3 run_eval.py --model $O --prompt prompts/v2_conf.txt --workers 3

log "phase 5d: routing sweeps (offline)"
for s in results/glm-5p3-flash_v2_conf_low.json results/glm-5p3-flash_v3_rubric_low.json results/glm-5p3-flash_v3_rubric_json_low.json results/nemotron-lightning-3p5-30b-a3b_v2_conf_none.json results/nemotron-lightning-3p5-30b-a3b_v3_rubric_json_none.json; do
  [ -f $s ] || continue; b=$(basename $s .json)
  python3 routing_sim.py $s results/glm-5p3_v1_plain.json --out results/routing_${b}__glm-5p3.json
  python3 routing_sim.py $s results/gpt-oss-120b_v1_plain.json --out results/routing_${b}__gpt-oss.json
done

log "phase 6: variance, 3 seeds, best small config (set BEST_PROMPT/BEST_EFFORT) and small baseline"
BEST_PROMPT=${BEST_PROMPT:-prompts/v3_rubric.txt}; BEST_EFFORT=${BEST_EFFORT:-low}; BEST_JSON=${BEST_JSON:---json-mode}
for s in 1 2 3; do
  python3 run_eval.py --model $G --prompt $BEST_PROMPT --effort $BEST_EFFORT $BEST_JSON --seed $s --workers 3 &
  python3 run_eval.py --model $G --prompt prompts/v1_plain.txt --seed $s --workers 3 &
done
wait

log "phase 7: free Muse Glimmer SFT (serverless, no deployment)"
sft/venv/bin/python sft_muse.py plan && sft/venv/bin/python sft_muse.py train && sft/venv/bin/python sft_muse.py eval

log "phase 8: chart"
python3 make_chart.py --best results/glm-5p3-flash_v3_rubric_json_low.json
log "done; ledger total:"; python3 -I -c "import csv; print(round(sum(float(r['cost']) for r in csv.DictReader(open('ledger.csv'))),4))"
