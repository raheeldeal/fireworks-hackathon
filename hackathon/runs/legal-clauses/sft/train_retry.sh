#!/bin/zsh
# The account allows 1 concurrent serverless training run on muse-glimmer-30b; retry every 5 min until we get the slot.
cd "$(dirname "$0")/.."; source ~/.zshrc 2>/dev/null
for i in {1..36}; do
  echo "$(date +%H:%M:%S) attempt $i" >> sft/train.log
  .venv311/bin/python sft/train_sft.py train >> sft/train.log 2>&1
  [[ -f sft/checkpoint.json ]] && { echo "$(date +%H:%M:%S) training done" >> sft/train.log; exit 0; }
  grep -q "maximum concurrent serverless training runs" sft/train.log || { echo "non-slot failure, stopping" >> sft/train.log; exit 1; }
  sleep 300
done
