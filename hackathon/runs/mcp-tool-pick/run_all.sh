#!/bin/zsh
# Reproduce everything after data generation. Waits for the Fireworks account to accept calls, then runs
# phases 4-8 and submits the free SFT job. Idempotent: skips result files that already exist.
source ~/.zshrc >/dev/null 2>&1
cd "$(dirname "$0")"
P=prompts/v1_plain.txt; R=prompts/v2_rubric.txt; T=prompts/v3_top3.txt; J=prompts/v4_json.txt
NEMO=nemotron-lightning-3p5-30b-a3b; FLASH=glm-5p3-flash
log() { echo "[$(date +%H:%M:%S)] $*"; }

# 0. wait for the account (HTTP 412 = suspended)
wait_account() {
  while true; do
    code=$(curl -s -o /dev/null -w "%{http_code}" https://api.fireworks.ai/inference/v1/chat/completions -H "Authorization: Bearer $FIREWORKS_API_KEY" -H "Content-Type: application/json" -d "{\"model\":\"accounts/fireworks/models/$NEMO\",\"max_tokens\":1,\"messages\":[{\"role\":\"user\",\"content\":\"hi\"}]}")
    [[ "$code" == "200" ]] && return
    log "account not ready (HTTP $code); sleeping 300s"; sleep 300
  done
}
wait_account; log "account OK, starting"

run() { # run <model> <tag> <args...>  (skips if results/<model>__<tag>__s<seed>.json exists)
  local m=$1 tag=$2; shift 2; local seed=0 prev=""
  for a in "$@"; do [[ "$prev" == "--seed" ]] && seed=$a; prev=$a; done
  local out=results/${m}__${tag}__s${seed}.json
  [[ -f $out ]] && { log "skip $out"; return; }
  wait_account; log "run $m $tag seed $seed"
  python3 run_eval.py --model $m --tag $tag "$@" --out $out > results/log_${m}__${tag}__s${seed}.txt 2>&1 || log "FAILED $m $tag"
}

# 4. baselines (model defaults; logprobs on small models for routing)
run $NEMO v1_plain --prompt $P --logprobs --workers 4 &
run $FLASH v1_plain --prompt $P --logprobs --workers 4 &
wait
run gpt-oss-120b v1_plain --prompt $P --workers 4 &
run deepseek-v4p1-flash v1_plain --prompt $P --workers 4 &
wait
run glm-5p3 v1_plain --prompt $P --workers 4 &
run kimi-k3 v1_plain --prompt $P --workers 3 --limit 100 &
wait

# 7 (part 1). free SFT job: submit early, poll at the end
[[ -f results/sft_job.json ]] || python3 sft_submit.py submit > results/log_sft_submit.txt 2>&1 || log "SFT submit failed (see results/log_sft_submit.txt)"

# 5. interventions on the two small models
run $NEMO v1_plain+rnone --prompt $P --reasoning none --logprobs --workers 4 &
run $FLASH v1_plain+rlow --prompt $P --reasoning low --logprobs --workers 4 &
wait
run $NEMO v2_rubric --prompt $R --logprobs --workers 4 &
run $FLASH v2_rubric --prompt $R --logprobs --workers 4 &
wait
run $NEMO v1_plain+5shot --prompt $P --shots 5 --logprobs --workers 4 &
run $FLASH v1_plain+5shot --prompt $P --shots 5 --logprobs --workers 4 &
wait
run $NEMO v4_json --prompt $J --json --workers 4 &
run $FLASH v4_json --prompt $J --json --workers 4 &
wait
run $NEMO v3_top3 --prompt $T --workers 4 &
run $FLASH v3_top3 --prompt $T --workers 4 &
wait
run $NEMO v1_plain+retr10 --prompt $P --retrieve 10 --logprobs --workers 4 &
run $FLASH v1_plain+retr10 --prompt $P --retrieve 10 --logprobs --workers 4 &
wait
run $NEMO v1_plain+retr20 --prompt $P --retrieve 20 --logprobs --workers 4 &
run $NEMO v2_rubric+rnone --prompt $R --reasoning none --logprobs --workers 4 &
wait
run $NEMO v2_rubric+5shot --prompt $R --shots 5 --logprobs --workers 4 &
run $FLASH v2_rubric+5shot --prompt $R --shots 5 --logprobs --workers 4 &
wait

# 5d. routing (offline, exact; no extra calls)
for s in ${NEMO}__v1_plain__s0 ${NEMO}__v2_rubric__s0 ${FLASH}__v1_plain__s0; do
  [[ -f results/$s.json ]] && python3 route_sim.py results/$s.json results/glm-5p3__v1_plain__s0.json --out results/route__${s%%__s0}-to-glm-5p3.json > results/log_route_${s}.txt 2>&1
done
[[ -f results/${NEMO}__v2_rubric__s0.json ]] && python3 route_sim.py results/${NEMO}__v2_rubric__s0.json results/kimi-k3__v1_plain__s0.json --out results/route__${NEMO}__v2_rubric-to-kimi-k3.json > results/log_route_kimi.txt 2>&1

# 6. variance: baseline and best small config, seeds 1 and 2 (seed 0 exists)
best=$(python3 - <<'PY'
import json,glob
best=None
for p in glob.glob("results/*__s0.json"):
    d=json.load(open(p)); m=d["model"].split("/")[-1]
    if m in ("nemotron-lightning-3p5-30b-a3b","glm-5p3-flash") and "retr" not in d["tag"] and d["tag"]!="v1_plain":
        if best is None or d["accuracy"]>best[0]: best=(d["accuracy"],m,d["tag"],p)
print(best[1], best[2]) if best else print("")
PY
)
read bm bt <<< "$best"; log "best small config: $bm $bt"
for seed in 1 2; do
  run $NEMO v1_plain --prompt $P --logprobs --seed $seed --workers 4 &
  if [[ -n "$bm" ]]; then
    args=(--prompt prompts/${bt%%+*}.txt); [[ $bt == *"+rnone"* ]] && args+=(--reasoning none); [[ $bt == *"+rlow"* ]] && args+=(--reasoning low)
    [[ $bt == *"+5shot"* ]] && args+=(--shots 5); [[ $bt == *"json"* ]] && args+=(--json)
    run $bm $bt "${args[@]}" --seed $seed --workers 4 &
  fi
  wait
done

# 8. chart + table
python3 make_chart.py; python3 summarize.py > results/table.md; python3 fw.py
# 7 (part 2). poll SFT job
[[ -f results/sft_job.json ]] && python3 sft_submit.py poll > results/log_sft_poll.txt 2>&1
log "ALL DONE"
