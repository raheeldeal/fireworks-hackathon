#!/bin/zsh
# Final bounded retry: poll the muse-glimmer-30b training slot every 60 s for up to 3 h.
# On success, ft/finish_phase7.py appends the phase-7 rows to RESULTS.md.
cd /Users/raheelahmed/fireworks-hackathon/hackathon/runs/product-json
source ~/.zshrc >/dev/null 2>&1
LOG=ft/sft_retry2.log
END=$(( $(date +%s) + 3*3600 ))
n=0
while [ $(date +%s) -lt $END ]; do
  n=$((n+1)); echo "attempt $n $(date +%H:%M)" >> $LOG
  ./ft/venv/bin/python ft/sft_muse.py --epochs 1 --base-limit 20 --tuned-limit 100 > ft/sft_run.log 2>&1
  rc=$?
  if [ $rc -eq 0 ]; then echo "SFT DONE $(date +%H:%M)" >> $LOG; python3 ft/finish_phase7.py >> $LOG 2>&1; exit 0; fi
  if ! grep -q "maximum concurrent serverless training runs" ft/sft_run.log; then echo "SFT FAILED (not slot) $(date +%H:%M)" >> $LOG; tail -5 ft/sft_run.log >> $LOG; exit 1; fi
  sleep 60
done
echo "gave up after 3h of 60-s slot retries $(date +%H:%M)" >> $LOG
exit 1
