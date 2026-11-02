#!/bin/zsh
# Runs every config in the agreed order. Each run re-reads TEST_HASH and test.jsonl.
source ~/.zshrc >/dev/null 2>&1
cd "$(dirname "$0")"
PY=../.venv/bin/python
for c in validate_only repair1 vote3 route_big prune_repair1 repair1_fewshot; do
  w=8; [[ $c == vote3 || $c == route_big ]] && w=5
  $PY run_harness.py --config $c --workers $w 2>&1 | tee -a run_all.log
done
