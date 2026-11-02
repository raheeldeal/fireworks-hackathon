#!/bin/bash
# Full protocol sweep for code-fix. Idempotent: every stage skips if its results file exists.
# Usage: bash sweep.sh            (needs FIREWORKS_API_KEY; ~$1.8 total at probe-measured token counts)
set -u
cd "$(dirname "$0")"
source ~/.zshrc >/dev/null 2>&1 || true
export FIREWORKS_API_KEY
M=accounts/fireworks/models
run() { # run <out-file> <args...>
  local out=$1; shift
  if [ -s "results/$out" ]; then echo "skip results/$out"; return; fi
  python3 run_eval.py "$@" --out "results/$out" 2>&1 | tail -n 3 | tee -a results/sweep.log
}
echo "=== phase 4: baselines ===" | tee -a results/sweep.log
run nemotron-lightning-3p5-30b-a3b_v1_plain.json --model $M/nemotron-lightning-3p5-30b-a3b --prompt prompts/v1_plain.txt --max-tokens 4096
run glm-5p3-flash_v1_plain.json                  --model $M/glm-5p3-flash --prompt prompts/v1_plain.txt
run gpt-oss-120b_v1_plain.json                   --model $M/gpt-oss-120b --prompt prompts/v1_plain.txt
run deepseek-v4p1-flash_v1_plain.json            --model $M/deepseek-v4p1-flash --prompt prompts/v1_plain.txt
run glm-5p3_v1_plain.json                        --model $M/glm-5p3 --prompt prompts/v1_plain.txt
run kimi-k3_v1_plain_n100.json                   --model $M/kimi-k3 --prompt prompts/v1_plain.txt --limit 100 --workers 2
BEST=$(python3 pick_best_small.py); B=${BEST##*/}
echo "=== phase 5: interventions on best small = $B ===" | tee -a results/sweep.log
MT=2048; [ "$B" = nemotron-lightning-3p5-30b-a3b ] && MT=4096
run ${B}_v2_rubric.json         --model $BEST --prompt prompts/v2_rubric.txt --max-tokens $MT
run ${B}_v1_plain_5shot.json    --model $BEST --prompt prompts/v1_plain.txt --shots 5 --max-tokens $MT
run ${B}_v1_plain_json.json     --model $BEST --prompt prompts/v1_plain.txt --json --max-tokens $MT
run ${B}_v1_plain_conf.json     --model $BEST --prompt prompts/v1_plain.txt --confidence --max-tokens $MT
# routing: small -> glm-5p3 (large), offline from the two temp-0 result files
python3 route.py --small results/${B}_v1_plain.json      --large results/glm-5p3_v1_plain.json --signal verify            | tee -a results/sweep.log
python3 route.py --small results/${B}_v1_plain_conf.json --large results/glm-5p3_v1_plain.json --signal self --thresholds 50,70,90,100 | tee -a results/sweep.log
python3 route.py --small results/${B}_v1_plain.json      --large results/glm-5p3_v1_plain.json --signal tokens --thresholds 300,600,1200 | tee -a results/sweep.log
echo "=== phase 6: variance (3 seeds) ===" | tee -a results/sweep.log
BESTCFG=$(python3 - <<PY
import json,glob
c=[(json.load(open(p))['accuracy'],p) for p in glob.glob('results/${B}_v*.json') if 'seed' not in p]
print(max(c)[1])
PY
)
echo "best small config file: $BESTCFG" | tee -a results/sweep.log
ARGS="--prompt prompts/v1_plain.txt"; case "$BESTCFG" in *v2_rubric*) ARGS="--prompt prompts/v2_rubric.txt";; *5shot*) ARGS="--prompt prompts/v1_plain.txt --shots 5";; *_json*) ARGS="--prompt prompts/v1_plain.txt --json";; esac
for s in 1 2; do
  run ${B}_v1_plain_seed$s.json --model $BEST --prompt prompts/v1_plain.txt --seed $s --max-tokens $MT
  run $(basename $BESTCFG .json)_seed$s.json --model $BEST $ARGS --seed $s --max-tokens $MT
done
python3 variance.py results/${B}_v1_plain.json results/${B}_v1_plain_seed1.json results/${B}_v1_plain_seed2.json | tee -a results/sweep.log
[ "$BESTCFG" != "results/${B}_v1_plain.json" ] && python3 variance.py $BESTCFG ${BESTCFG%.json}_seed1.json ${BESTCFG%.json}_seed2.json | tee -a results/sweep.log
echo "=== phase 8: chart ===" | tee -a results/sweep.log
python3 chart.py | tee -a results/sweep.log
python3 compare.py --md results/*_v1_plain*.json results/*_v2*.json results/ROUTE_*.json 2>/dev/null | tee results/table.md
echo "ledger total: $(python3 -c "import run_eval; print(round(run_eval.ledger_total(),4))")" | tee -a results/sweep.log
