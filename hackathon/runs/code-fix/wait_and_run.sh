#!/bin/bash
# Poll the Fireworks API every 5 min; when the account is un-suspended, run the sweep once.
cd "$(dirname "$0")"; source ~/.zshrc >/dev/null 2>&1
for i in $(seq 1 96); do   # up to 8 hours
  code=$(curl -s -o /dev/null -w "%{http_code}" -m 30 https://api.fireworks.ai/inference/v1/chat/completions -H "Authorization: Bearer $FIREWORKS_API_KEY" -H "Content-Type: application/json" -d '{"model":"accounts/fireworks/models/glm-5p3-flash","max_tokens":1,"messages":[{"role":"user","content":"hi"}]}')
  echo "$(date +%H:%M:%S) probe HTTP $code" >> results/wait.log
  if [ "$code" = "200" ]; then echo "API back at $(date)" >> results/wait.log; bash sweep.sh >> results/sweep_full.log 2>&1; echo "SWEEP DONE $(date)" >> results/wait.log; exit 0; fi
  sleep 300
done
echo "gave up after 8h" >> results/wait.log; exit 1
