#!/bin/zsh
# One cheap call to see whether the account is back. Prints HTTP code.
source ~/.zshrc >/dev/null 2>&1
curl -s -o /dev/null -w "%{http_code}\n" https://api.fireworks.ai/inference/v1/chat/completions -H "Authorization: Bearer $FIREWORKS_API_KEY" -H "Content-Type: application/json" -d '{"model":"accounts/fireworks/models/nemotron-lightning-3p5-30b-a3b","max_tokens":4,"temperature":0,"messages":[{"role":"user","content":"OK"}]}'
