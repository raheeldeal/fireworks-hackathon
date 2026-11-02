#!/bin/zsh
# Poll Fireworks every 15 min with a 5-token call until it returns HTTP 200. Exits 0 when unblocked.
source ~/.zshrc >/dev/null 2>&1
LOG="$(dirname "$0")/results/poll_log.txt"
while true; do
  code=$(curl -s -o /dev/null -w "%{http_code}" https://api.fireworks.ai/inference/v1/chat/completions \
    -H "Authorization: Bearer $FIREWORKS_API_KEY" -H "Content-Type: application/json" \
    -d '{"model":"accounts/fireworks/models/glm-5p3-flash","max_tokens":5,"messages":[{"role":"user","content":"hi"}]}')
  echo "$(date +%Y-%m-%dT%H:%M:%S) HTTP $code" >> "$LOG"
  if [ "$code" = "200" ]; then echo "UNBLOCKED at $(date)"; exit 0; fi
  sleep 900
done
