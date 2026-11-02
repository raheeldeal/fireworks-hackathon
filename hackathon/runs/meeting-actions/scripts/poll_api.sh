#!/bin/bash
# Probe Fireworks every 10 minutes with a 5-token call; exit 0 when it returns 200.
source ~/.zshrc 2>/dev/null
cd "$(dirname "$0")/.."
while true; do
  code=$(curl -s -o /tmp/ma_probe.json -w "%{http_code}" https://api.fireworks.ai/inference/v1/chat/completions \
    -H "Authorization: Bearer $FIREWORKS_API_KEY" -H "Content-Type: application/json" \
    -d '{"model":"accounts/fireworks/models/glm-5p3-flash","max_tokens":5,"temperature":0,"reasoning_effort":"low","messages":[{"role":"user","content":"Say OK"}]}')
  echo "$(date '+%H:%M:%S') HTTP $code" >> results/poll.log
  if [ "$code" = "200" ]; then
    python3 - <<'PY'
import json,sys; sys.path.insert(0,"scripts"); import fw
d=json.load(open("/tmp/ma_probe.json")); u=d.get("usage",{})
fw.log("accounts/fireworks/models/glm-5p3-flash",u.get("prompt_tokens",0),u.get("completion_tokens",0),"poll")
PY
    echo "API restored at $(date)" >> results/poll.log; exit 0
  fi
  sleep 600
done
