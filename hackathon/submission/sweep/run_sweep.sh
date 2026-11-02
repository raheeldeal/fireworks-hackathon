#!/bin/zsh
# Today's sweep. Idempotent: skips a run if its results file exists. Three chains in parallel, 4 workers each.
source ~/.zshrc >/dev/null 2>&1
cd "$(dirname "$0")"
P=../prompts/v1_plain.txt
run() { # model tag extra-args...
  local m=$1 t=$2; shift 2
  [[ -f results/${m}__${t}__s0.json ]] && { echo "skip $m $t"; return; }
  python3 run.py --model $m --prompt $P --tag $t --logprobs --workers 4 "$@" > logs/${m}__${t}.txt 2>&1
  tail -2 logs/${m}__${t}.txt | head -1
}
NEMO=nemotron-lightning-3p5-30b-a3b; FLASH=glm-5p3-flash
( run $NEMO v1_plain --max_tokens 1024
  run $NEMO v1_plain+mt512 --max_tokens 512
  run $NEMO v1_plain+mt4096 --max_tokens 4096
  run $NEMO v1_plain+rnone+mt512 --max_tokens 512 --reasoning none
  run $NEMO v1_plain+rnone+mt4096 --max_tokens 4096 --reasoning none
  run $NEMO v5_conf+rnone+mt512 --max_tokens 512 --reasoning none --prompt prompts/v5_conf.txt --json
) &
( run $FLASH v1_plain --max_tokens 1024
  run $FLASH v1_plain+mt512 --max_tokens 512
  run $FLASH v1_plain+mt4096 --max_tokens 4096
  run $FLASH v1_plain+rlow+mt512 --max_tokens 512 --reasoning low
  run $FLASH v1_plain+rlow+mt4096 --max_tokens 4096 --reasoning low
  run $FLASH v5_conf+rlow+mt512 --max_tokens 512 --reasoning low --prompt prompts/v5_conf.txt --json
) &
( run gpt-oss-120b v1_plain --max_tokens 1024
  run deepseek-v4p1-flash v1_plain --max_tokens 1024
) &
wait
echo SWEEP DONE; python3 -c "import sys; sys.path.insert(0,'..'); import fw, os; fw.LEDGER='ledger.csv'; print('ledger', fw.ledger_total())"
