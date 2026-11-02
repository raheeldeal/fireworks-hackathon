#!/bin/zsh
# Wait for sft_serverless.py to exit (its tuned eval runs inside the same process), then delete the training session
# so the account's single serverless-training slot is freed for the other runs.
cd "$(dirname "$0")"; source ~/.zshrc >/dev/null 2>&1
while pgrep -f sft_serverless.py >/dev/null; do sleep 15; done
SID=$(grep -o "session=ts-[a-f0-9]*" results/sft.log | head -1 | cut -d= -f2)
echo "$(date '+%H:%M:%S') sft process exited; deleting $SID"
curl -s -X DELETE -H "Authorization: Bearer $FIREWORKS_API_KEY" "https://api.fireworks.ai/v1/accounts/raheeldeal/trainingSessions/$SID" -w "\nHTTP %{http_code}\n"
sleep 5
curl -s -H "Authorization: Bearer $FIREWORKS_API_KEY" "https://api.fireworks.ai/v1/accounts/raheeldeal/trainingSessions/$SID" -w "\nHTTP %{http_code}\n" | tail -c 400
