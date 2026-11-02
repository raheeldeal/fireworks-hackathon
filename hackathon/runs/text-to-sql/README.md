# Text-to-SQL on Spider: reproduce every number

All commands run from this folder with Python 3.10 (stdlib + matplotlib) and `FIREWORKS_API_KEY` exported.

## 0. Data (already done; re-running is deterministic)
```bash
mkdir -p raw/zip && curl -L -o raw/zip/spider_data.zip https://huggingface.co/datasets/HAL-9001/spider-databases/resolve/main/spider_data.zip
shasum -a 256 raw/zip/spider_data.zip   # 00636695dabed6b5f4b8328a16b13e069a2f16591d5efcce57660669c85b121b
(cd raw/zip && unzip -q spider_data.zip)
python3 build_data.py                    # writes data/test.jsonl (locked) and data/train.jsonl
python3 ../common/check_leak.py data/test.jsonl data/train.jsonl data/sft_train.jsonl
shasum -a 256 data/test.jsonl            # must start 4efe94e1f88833af
```
`data/test.jsonl` is locked; `build_data.py` is kept for provenance only. If you re-run it, confirm the hash is unchanged.

## 1. Scorer self-test
```bash
python3 score.py
```

## 2. Baselines (one line per model; kimi-k3 capped at 100 rows)
```bash
for m in nemotron-lightning-3p5-30b-a3b glm-5p3-flash gpt-oss-120b deepseek-v4p1-flash; do
  python3 run_eval.py --model accounts/fireworks/models/$m --prompt prompts/v1_plain.txt; done
python3 run_eval.py --model accounts/fireworks/models/glm-5p3 --prompt prompts/v1_plain.txt --extra '{"reasoning_effort":"low"}'
python3 run_eval.py --model accounts/fireworks/models/kimi-k3 --prompt prompts/v1_plain.txt --limit 100
python3 compare.py
```

## 3. Harness interventions
```bash
python3 run_eval.py --model <small> --prompt prompts/v2_rubric.txt
python3 run_eval.py --model <small> --prompt prompts/v3_fewshot.txt
python3 run_eval.py --model <small> --prompt prompts/v2_rubric.txt --extra '{"response_format":{"type":"json_object"}}' --tag json
python3 route.py results/<small>.json results/<large>.json --out-prefix results/route_<small>_<large>
```

## 4. Variance (3 seeds = 3 request orders at temperature 0)
```bash
for s in 1 2 3; do python3 run_eval.py --model <small> --prompt <best prompt> --seed $s; done
```

## 5. Fine-tuning
```bash
python3 make_sft.py                       # data/sft_train.jsonl, ~125k tokens
python3 sft_job.py submit                 # creates the dataset, uploads it, starts one LoRA SFT job; prints the job name
python3 sft_job.py status <job>           # poll
```

## 6. Chart and tables
```bash
python3 compare.py
python3 chart.py                          # frontier.png
```
`ledger.csv` holds every paid call's token counts and cost; the Spend line in RESULTS.md is its sum.
