#!/bin/bash
# Waits for the Fireworks account to come back (HTTP 200 on a 5-token call, ~$0.000001), then runs run_all.sh.
# Polls every 5 minutes for up to 9 hours. Log: wait_and_run.log
cd "$(dirname "$0")"
source ~/.zshrc >/dev/null 2>&1
for i in $(seq 1 108); do
  code=$(curl -sS -o /dev/null -w "%{http_code}" --max-time 30 https://api.fireworks.ai/inference/v1/chat/completions \
    -H "Authorization: Bearer $FIREWORKS_API_KEY" -H "Content-Type: application/json" \
    -d '{"model":"accounts/fireworks/models/nemotron-lightning-3p5-30b-a3b","max_tokens":2,"messages":[{"role":"user","content":"hi"}]}')
  echo "$(date +%H:%M:%S) probe $i -> HTTP $code"
  if [ "$code" = "200" ]; then
    echo "account is back; starting run_all.sh"
    ./run_all.sh
    echo "run_all.sh finished with exit $?"
    exit 0
  fi
  sleep 300
done
echo "gave up after 9 hours; account still suspended"
exit 2
