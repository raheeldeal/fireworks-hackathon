#!/bin/zsh
# Second retry window: other sessions grab the single muse-glimmer-30b slot between 5-minute retries,
# so poll every 60 s for up to 2 h. On success, score the checkpoint and free the slot immediately.
cd "$(dirname "$0")/.."; source ~/.zshrc 2>/dev/null
for i in {1..120}; do
  echo "$(date +%H:%M:%S) attempt2 $i" >> sft/train.log
  .venv311/bin/python sft/train_sft.py train >> sft/train.log 2>&1
  if [[ -f sft/checkpoint.json ]]; then
    echo "$(date +%H:%M:%S) training done; eval then cleanup" >> sft/train.log
    .venv311/bin/python sft/train_sft.py eval >> sft/train.log 2>&1
    .venv311/bin/python sft/train_sft.py cleanup >> sft/train.log 2>&1
    echo "$(date +%H:%M:%S) eval done" >> sft/train.log
    exit 0
  fi
  tail -3 sft/train.log | grep -q "maximum concurrent serverless training runs" || { echo "non-slot failure, stopping" >> sft/train.log; exit 1; }
  sleep 60
done
echo "$(date +%H:%M:%S) retry window 2 exhausted" >> sft/train.log
