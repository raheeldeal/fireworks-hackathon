#!/bin/zsh
# Poll the account every 5 min for up to 8 h; when a call succeeds, run run_all.sh.
cd "$(dirname "$0")"
for i in $(seq 1 96); do
  code=$(./probe.sh)
  echo "$(date '+%H:%M:%S') probe HTTP $code"
  if [[ "$code" == "200" ]]; then ./run_all.sh; exit 0; fi
  sleep 300
done
echo "gave up after 8h"; exit 1
