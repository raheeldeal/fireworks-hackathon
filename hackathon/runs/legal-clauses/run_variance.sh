#!/bin/zsh
# Phase 6: best small config (glm-5p3-flash + JSON mode) and its plain baseline, two more seeds each (shuffled order).
cd "$(dirname "$0")"; source ~/.zshrc 2>/dev/null
log() { echo "$(date +%H:%M:%S) $*" | tee -a results/variance.log; }
M=accounts/fireworks/models/glm-5p3-flash
for s in 11 13; do
  python3 run_eval.py --model $M --prompt prompts/v1_plain.txt --seed $s --reasoning-effort low --max-tokens 2048 --logprobs --workers 3 --out results/glm-5p3-flash_v1_plain_s$s.json >> results/variance.log 2>&1
  python3 run_eval.py --model $M --prompt prompts/v4_json.txt --json-mode --tag nothink --seed $s --no-think --max-tokens 2048 --logprobs --workers 3 --out results/glm-5p3-flash_v4_json_nothink_s$s.json >> results/variance.log 2>&1
done
log "variance done"
