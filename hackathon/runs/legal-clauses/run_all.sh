#!/bin/zsh
# Driver: wait for the Fireworks account to come back (probe every 15 min), then run the baseline sweep and
# cheap interventions in budget order. Idempotent: skips any result file that already exists.
cd "$(dirname "$0")"; source ~/.zshrc 2>/dev/null
log() { echo "$(date +%H:%M:%S) $*" | tee -a results/driver.log; }
probe() { curl -s -o /dev/null -w "%{http_code}" -H "Authorization: Bearer $FIREWORKS_API_KEY" -H "Content-Type: application/json" \
  -d '{"model":"accounts/fireworks/models/nemotron-lightning-3p5-30b-a3b","max_tokens":5,"messages":[{"role":"user","content":"hi"}]}' \
  https://api.fireworks.ai/inference/v1/chat/completions; }
while true; do c=$(probe); log "probe HTTP $c"; [[ "$c" == "200" ]] && break; sleep 900; done
log "account live; starting sweep"
M=accounts/fireworks/models
run() { # out-name, then args
  local out=results/$1.json; shift
  [[ -f $out ]] && { log "skip $out"; return; }
  log "run $out"; python3 run_eval.py "$@" --out $out --reasoning-effort low --max-tokens 2048 --logprobs --workers 4 >> results/driver.log 2>&1
}
# phase 4 baselines, cheapest first
run nemotron-lightning-3p5-30b-a3b_v1_plain_s7 --model $M/nemotron-lightning-3p5-30b-a3b --prompt prompts/v1_plain.txt
run glm-5p3-flash_v1_plain_s7 --model $M/glm-5p3-flash --prompt prompts/v1_plain.txt
run gpt-oss-120b_v1_plain_s7 --model $M/gpt-oss-120b --prompt prompts/v1_plain.txt
run deepseek-v4p1-flash_v1_plain_s7 --model $M/deepseek-v4p1-flash --prompt prompts/v1_plain.txt
run glm-5p3_v1_plain_s7 --model $M/glm-5p3 --prompt prompts/v1_plain.txt
run kimi-k3_v1_plain_s7 --model $M/kimi-k3 --prompt prompts/v1_plain.txt --limit 100
# phase 5 b/c on the two small models
run nemotron-lightning-3p5-30b-a3b_v3_fewshot_s7 --model $M/nemotron-lightning-3p5-30b-a3b --prompt prompts/v3_fewshot.txt --fewshot 5
run nemotron-lightning-3p5-30b-a3b_v4_json_s7 --model $M/nemotron-lightning-3p5-30b-a3b --prompt prompts/v4_json.txt --json-mode
run glm-5p3-flash_v3_fewshot_s7 --model $M/glm-5p3-flash --prompt prompts/v3_fewshot.txt --fewshot 5
run glm-5p3-flash_v4_json_s7 --model $M/glm-5p3-flash --prompt prompts/v4_json.txt --json-mode
log "sweep done"; python3 compare.py | tee -a results/driver.log
