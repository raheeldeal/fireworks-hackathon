#!/bin/bash
# Poll Fireworks every 10 minutes with a 5-token call; exit 0 when it returns 200.
trap "" URG HUP
source ~/.zshrc >/dev/null 2>&1
while true; do
  code=$(curl -s -o /tmp/fw_poll_body.txt -w "%{http_code}" https://api.fireworks.ai/inference/v1/chat/completions \
    -H "Authorization: Bearer $FIREWORKS_API_KEY" -H "Content-Type: application/json" \
    -d '{"model":"accounts/fireworks/models/nemotron-lightning-3p5-30b-a3b","max_tokens":5,"messages":[{"role":"user","content":"hi"}]}')
  echo "$(date +%H:%M:%S) HTTP $code"
  if [ "$code" = "200" ]; then echo "API BACK"; exit 0; fi
  sleep 600
done
