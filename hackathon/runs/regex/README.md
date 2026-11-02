# Natural language → Python regex (mock hackathon run)

Every number in `RESULTS.md` comes from the commands below. Nothing is mocked. Prices are the serverless standard rates in `../PROTOCOL.md`.

## Setup (once)
```bash
cd hackathon/runs/regex
python3 -m venv venv && venv/bin/pip install exrex matplotlib            # Python 3.10, eval + data
source ~/.zshrc                                                            # FIREWORKS_API_KEY
```
Fine-tuning only: `pyenv install 3.11 && ~/.pyenv/versions/3.11.9/bin/python -m venv venv311 && venv311/bin/pip install "fireworks-ai[training]>=1.2.30" transformers`

## 1. Data (deterministic; re-running gives byte-identical files)
```bash
curl -sL -o raw/dl/deep-regex.zip https://github.com/nicholaslocascio/deep-regex/archive/refs/heads/master.zip && (cd raw/dl && unzip -q -o deep-regex.zip)
venv/bin/python build_data.py                      # data/test.jsonl (200 rows, ~15 min of exrex sampling) + data/train.jsonl (500) + data/heldout.jsonl (100)
venv/bin/python build_data.py --train-only         # same train/heldout files in 2 s, reusing the locked test file
shasum -a 256 data/test.jsonl                      # ef955dce4c2c19c52b0b512d073416019193dc3c3be4d216c0a844cb435358c7
venv/bin/python make_sft.py --few-shot && venv/bin/python make_sft.py          # data/fewshot5.jsonl, data/sft_train.jsonl
venv/bin/python ../common/check_leak.py data/test.jsonl data/train.jsonl data/sft_train.jsonl data/fewshot5.jsonl data/heldout.jsonl
```
Each test row: `text` (description), `gold` (regex), `positives[10]`, `negatives[10]`. The strings are stored in the file, so scoring never re-generates anything.

## 2. Scorer
```bash
venv/bin/python score.py --test                    # 9 unit cases, must print ALL PASS
```

## 3. Baseline sweep (plain prompt, temperature 0, max_tokens 512, reasoning off/low)
```bash
M=accounts/fireworks/models
venv/bin/python run_eval.py --model $M/nemotron-lightning-3p5-30b-a3b --prompt prompts/v1_plain.txt --reasoning-effort none
venv/bin/python run_eval.py --model $M/glm-5p3-flash               --prompt prompts/v1_plain.txt --reasoning-effort low
venv/bin/python run_eval.py --model $M/gpt-oss-120b                --prompt prompts/v1_plain.txt --reasoning-effort low
venv/bin/python run_eval.py --model $M/deepseek-v4p1-flash         --prompt prompts/v1_plain.txt --reasoning-effort none
venv/bin/python run_eval.py --model $M/glm-5p3                     --prompt prompts/v1_plain.txt --reasoning-effort low
venv/bin/python run_eval.py --model $M/kimi-k3                     --prompt prompts/v1_plain.txt --reasoning-effort none --limit 100
venv/bin/python run_eval.py --model $M/glm-5p3                     --prompt prompts/v1_plain.txt --reasoning-effort low --max-tokens 2048 --tag mt2048   # 512 truncates 10 rows
for m in nemotron-lightning-3p5-30b-a3b deepseek-v4p1-flash glm-5p3-flash glm-5p3 gpt-oss-120b kimi-k3; do
  venv/bin/python run_eval.py --model $M/$m --prompt prompts/v1_plain.txt --repair results/${m}_v1_plain.json   # re-query rows lost to HTTP 429
done
venv/bin/python compare.py --md
```
Every run appends to `ledger.csv` and refuses to start once the ledger reaches $3.00. Runs tonight used `--workers 3` or `4`; the account rate limit is shared, so fewer workers = fewer `--repair` rows.

## 4. Harness interventions (best small model = glm-5p3-flash; gpt-oss-120b also run for rubric and JSON)
```bash
S=$M/glm-5p3-flash
venv/bin/python run_eval.py --model $S --prompt prompts/v2_rubric.txt --reasoning-effort low
venv/bin/python run_eval.py --model $M/gpt-oss-120b --prompt prompts/v2_rubric.txt --reasoning-effort low
venv/bin/python run_eval.py --model $S --prompt prompts/v1_plain.txt --few-shot data/fewshot5.jsonl --tag 5shot --reasoning-effort low
venv/bin/python run_eval.py --model $S --prompt prompts/v2_rubric.txt --few-shot data/fewshot5.jsonl --tag 5shot --reasoning-effort low
venv/bin/python run_eval.py --model $S --prompt prompts/v1_plain.txt --json-mode --tag json --reasoning-effort low
venv/bin/python run_eval.py --model $M/gpt-oss-120b --prompt prompts/v1_plain.txt --json-mode --tag json --reasoning-effort low
venv/bin/python run_eval.py --model $S --prompt prompts/v2_rubric.txt --logprobs --tag conf --reasoning-effort low
venv/bin/python run_eval.py --model $M/glm-5p3 --prompt prompts/v2_rubric.txt --reasoning-effort low --max-tokens 2048 --tag mt2048   # frontier with the same prompt
venv/bin/python run_eval.py --model $M/kimi-k3  --prompt prompts/v2_rubric.txt --reasoning-effort none --limit 100
venv/bin/python route.py results/glm-5p3-flash_v2_rubric_conf.json results/glm-5p3_v2_rubric_mt2048.json --thresholds 0.5 0.7 0.8 0.9 0.95 0.98
# held-out sanity check of the rubric prompt on 100 train rows it was not written from
venv/bin/python run_eval.py --model $S --prompt prompts/v1_plain.txt  --data data/heldout.jsonl --tag heldout --reasoning-effort low --out results/heldout_glm-5p3-flash_v1_plain.json
venv/bin/python run_eval.py --model $S --prompt prompts/v2_rubric.txt --data data/heldout.jsonl --tag heldout --reasoning-effort low --out results/heldout_glm-5p3-flash_v2_rubric.json
```

## 5. Variance (3 seeds = 3 shuffled orders at temperature 0)
```bash
for s in 1 2 3; do
  venv/bin/python run_eval.py --model $M/glm-5p3-flash --prompt prompts/v2_rubric.txt --seed $s --reasoning-effort low
  venv/bin/python run_eval.py --model $M/glm-5p3-flash --prompt prompts/v1_plain.txt  --seed $s --reasoning-effort low
done
```

## 6. Fine-tuning
```bash
venv311/bin/python sft_serverless.py --dry-run                 # token counts, no API
venv311/bin/python sft_serverless.py --train --epochs 2        # free Muse Glimmer 30B LoRA on the Serverless Training API (one run per account at a time: retry on "in use 1, limit 1")
venv311/bin/python sft_serverless.py --eval base               # untuned control
venv311/bin/python sft_serverless.py --eval <checkpoint path from results/sft_checkpoint.json>
bash sft_managed.sh                                            # managed SFT on qwen3-4b: documented only (firectl refuses mutating commands inside an agent; not scorable without a dedicated deployment)
```

## 7. Chart
```bash
venv/bin/python make_chart.py --best glm-5p3-flash_v2_rubric
```
