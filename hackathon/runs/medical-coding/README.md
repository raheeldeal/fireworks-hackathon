# Medical coding run: clinical note -> ICD-10-CM category codes

Everything here is reproducible with Python 3.10 and `FIREWORKS_API_KEY` (`source ~/.zshrc`). Run from this folder.

```bash
python3 score.py                                   # 7 unit tests for the scorer
python3 gen_data.py --workers 4                    # 500 synthetic notes with glm-5p3 -> data/all.jsonl (~$0.5)
python3 split_data.py                              # locks data/test.jsonl (180) and data/train.jsonl; prints sha256
python3 ../common/check_leak.py data/test.jsonl data/train.jsonl
python3 run_eval.py --model accounts/fireworks/models/glm-5p3-flash --prompt prompts/v1_plain.txt   # one baseline row
bash run_all.sh                                    # every row in RESULTS.md, in order
python3 route.py results/<small>.json results/<large>.json --thresholds 0.5 0.7 0.8 0.9
python3 compare.py                                 # the table
python3 chart.py                                   # frontier.png
```

Files: `SPEC.md` (task), `DECISIONS.md` (every judgment call, with times), `ledger.csv` (every paid call), `RESULTS.md` (judge format), `BUSINESS.md`, `PITCH.md`, `prompts/` (v1 plain, v2 rubric, v3 5-shot, v4 rubric+5-shot, v5 confidence for routing), `results/*.json` (one per run; `rows` has every prediction).

Metric: "accuracy" in all tables is mean per-note set-F1 between predicted and gold code sets; `exact_accuracy` is exact-set match. Codes outside the 60-code list are dropped; an output with zero in-list codes counts as invalid and scores 0.
