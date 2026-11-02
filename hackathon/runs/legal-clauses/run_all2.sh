#!/bin/zsh
# Second driver: waits for run_all.sh to finish (avoids stacking rate limits), then runs the no-think baselines
# for the models the first driver did not cover, and the phase-5 few-shot / JSON runs on the two small models.
cd "$(dirname "$0")"; source ~/.zshrc 2>/dev/null
log() { echo "$(date +%H:%M:%S) $*" | tee -a results/driver2.log; }
until grep -q "sweep done" results/driver.log 2>/dev/null; do sleep 30; done
log "driver 1 finished; starting no-think sweep"
M=accounts/fireworks/models
run() { local out=results/$1.json; shift
  [[ -f $out ]] && { log "skip $out"; return; }
  log "run $out"; python3 run_eval.py "$@" --out $out --no-think --max-tokens 2048 --logprobs --workers 4 >> results/driver2.log 2>&1
}
run nemotron-lightning-3p5-30b-a3b_v1_plain_nothink_s7 --model $M/nemotron-lightning-3p5-30b-a3b --prompt prompts/v1_plain.txt --tag nothink
run deepseek-v4p1-flash_v1_plain_nothink_s7 --model $M/deepseek-v4p1-flash --prompt prompts/v1_plain.txt --tag nothink
run glm-5p3_v1_plain_nothink_s7 --model $M/glm-5p3 --prompt prompts/v1_plain.txt --tag nothink
run kimi-k3_v1_plain_nothink_s7 --model $M/kimi-k3 --prompt prompts/v1_plain.txt --tag nothink --limit 100
run nemotron-lightning-3p5-30b-a3b_v3_fewshot_nothink_s7 --model $M/nemotron-lightning-3p5-30b-a3b --prompt prompts/v3_fewshot.txt --fewshot 5 --tag nothink
run nemotron-lightning-3p5-30b-a3b_v4_json_nothink_s7 --model $M/nemotron-lightning-3p5-30b-a3b --prompt prompts/v4_json.txt --json-mode --tag nothink
run glm-5p3-flash_v3_fewshot_nothink_s7 --model $M/glm-5p3-flash --prompt prompts/v3_fewshot.txt --fewshot 5 --tag nothink
run glm-5p3-flash_v4_json_nothink_s7 --model $M/glm-5p3-flash --prompt prompts/v4_json.txt --json-mode --tag nothink
log "sweep 2 done"; python3 compare.py | tee -a results/driver2.log
