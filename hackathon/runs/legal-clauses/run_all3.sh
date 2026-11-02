#!/bin/zsh
# Third driver: after sweep 2, run the rubric prompt on the two small models.
cd "$(dirname "$0")"; source ~/.zshrc 2>/dev/null
log() { echo "$(date +%H:%M:%S) $*" | tee -a results/driver3.log; }
until grep -q "sweep 2 done" results/driver2.log 2>/dev/null; do sleep 30; done
log "driver 2 finished; starting rubric runs"
M=accounts/fireworks/models
run() { local out=results/$1.json; shift
  [[ -f $out ]] && { log "skip $out"; return; }
  log "run $out"; python3 run_eval.py "$@" --out $out --no-think --max-tokens 2048 --logprobs --workers 4 >> results/driver3.log 2>&1
}
run nemotron-lightning-3p5-30b-a3b_v2_rubric_nothink_s7 --model $M/nemotron-lightning-3p5-30b-a3b --prompt prompts/v2_rubric.txt --tag nothink
run glm-5p3-flash_v2_rubric_nothink_s7 --model $M/glm-5p3-flash --prompt prompts/v2_rubric.txt --tag nothink
log "sweep 3 done"
