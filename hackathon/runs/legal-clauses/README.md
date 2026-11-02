# legal-clauses: reproduce every number in RESULTS.md

Run from this folder after `source ~/.zshrc` (sets `FIREWORKS_API_KEY`). Python 3.10 for everything except the fine-tune, which uses the 3.11 venv `.venv311`. Every API call appends a line to `ledger.csv` (timestamp, model, in_tokens, out_tokens, cost, note); `run_eval.py` refuses to start a call once the ledger reaches $3.00.

## 1. Data (locked; re-running is deterministic)
```
.venv/bin/python -I build_data.py                      # data/test.jsonl (199 rows) and data/train.jsonl (500 rows) from data/raw/*.parquet
python3 ../common/check_leak.py data/test.jsonl data/train.jsonl sft/train_chat.jsonl
sha256sum data/test.jsonl                              # 08f0ae5dc704e13b...
```
`data/raw/` holds the LEDGAR parquet files downloaded from `https://huggingface.co/api/datasets/coastalcph/lex_glue/parquet/ledgar/{train,validation,test}/0.parquet`. `data/labels.json` has the 100 labels with the one-line definitions used in every prompt.

## 2. Scorer
```
python3 score.py --test        # 7 unit cases incl. a wrong answer, an ambiguous answer and empty output
```

## 3. Baselines and prompt interventions (phases 4 and 5)
One row of the table is one `run_eval.py` call. Output file names are `results/<model>_<prompt>[_tag]_s<seed>.json`.
```
M=accounts/fireworks/models
# plain prompt, thinking off (falls back to reasoning_effort=low on models that reject the switch)
python3 run_eval.py --model $M/nemotron-lightning-3p5-30b-a3b --prompt prompts/v1_plain.txt --tag nothink --no-think --max-tokens 2048 --logprobs
python3 run_eval.py --model $M/deepseek-v4p1-flash --prompt prompts/v1_plain.txt --tag nothink --no-think --max-tokens 2048 --logprobs
python3 run_eval.py --model $M/glm-5p3 --prompt prompts/v1_plain.txt --tag nothink --no-think --max-tokens 2048 --logprobs
python3 run_eval.py --model $M/kimi-k3 --prompt prompts/v1_plain.txt --tag nothink80 --no-think --max-tokens 2048 --logprobs --limit 80
# glm-5p3-flash and gpt-oss-120b baselines were run with --reasoning-effort low (identical request to the fallback)
python3 run_eval.py --model $M/glm-5p3-flash --prompt prompts/v1_plain.txt --reasoning-effort low --max-tokens 2048 --logprobs
python3 run_eval.py --model $M/gpt-oss-120b --prompt prompts/v1_plain.txt --reasoning-effort low --max-tokens 2048 --logprobs
# nemotron with thinking left on (the 33% row)
python3 run_eval.py --model $M/nemotron-lightning-3p5-30b-a3b --prompt prompts/v1_plain.txt --reasoning-effort low --max-tokens 2048 --logprobs
# interventions (same flags, different prompt)
python3 run_eval.py --model $M/glm-5p3-flash --prompt prompts/v4_json.txt --json-mode --tag nothink --no-think --max-tokens 2048 --logprobs
python3 run_eval.py --model $M/glm-5p3-flash --prompt prompts/v3_fewshot.txt --fewshot 5 --tag nothink --no-think --max-tokens 2048 --logprobs
python3 run_eval.py --model $M/glm-5p3-flash --prompt prompts/v2_rubric.txt --tag nothink --no-think --max-tokens 2048 --logprobs
```
The drivers that ran these overnight are `run_all.sh`, `run_all2.sh`, `run_all3.sh`, `run_variance.sh` (logs in `results/driver*.log`, `results/variance.log`). If a run has rows with `finish` starting with `error` (rate-limit exhaustion), `python3 fix_errors.py results/<run>.json` re-runs only those rows.

Rubric rules were derived from a dev run on 200 training clauses: `python3 run_eval.py --model $M/nemotron-lightning-3p5-30b-a3b --prompt prompts/v1_plain.txt --data data/train.jsonl --limit 200 --seed 5 --no-think --max-tokens 2048 --logprobs --out results/dev_nemotron_train200_v1.json`.

## 4. Routing (phase 5d, simulation from result files)
```
python3 route.py results/nemotron-lightning-3p5-30b-a3b_v1_plain_nothink_s7.json results/deepseek-v4p1-flash_v1_plain_nothink_s7.json --thresholds 0.5 0.7 0.9 0.95 0.99
python3 route.py results/glm-5p3-flash_v1_plain_s7.json results/deepseek-v4p1-flash_v1_plain_nothink_s7.json --thresholds 0.5 0.7 0.9 0.95 0.99
```
(also run against `glm-5p3_v1_plain_nothink_s7.json` as the large model)

## 5. Variance (phase 6)
`./run_variance.sh` = glm-5p3-flash plain and JSON mode with `--seed 11` and `--seed 13` (seed 7 is the original).

## 6. Fine-tune (phase 7, free Muse Glimmer 30B LoRA)
```
.venv311/bin/python sft/train_sft.py prepare   # sft/train_chat.jsonl from data/train.jsonl
.venv311/bin/python sft/train_sft.py plan      # token stats, steps, expected sampling cost
.venv311/bin/python sft/train_sft.py train     # serverless LoRA SFT; writes sft/session.json, sft/metrics.jsonl, sft/checkpoint.json
.venv311/bin/python sft/train_sft.py eval      # samples the checkpoint on data/test.jsonl -> results/muse-glimmer-30b-lora_v5_short_sft_s7.json
.venv311/bin/python sft/train_sft.py cleanup   # deletes the training session (frees the account's single slot)
```
`sft/train_retry.sh` wraps `train` with 5-minute retries for the slot; `sft/train_retry2.sh` polls every 60 s and chains eval + cleanup (this is what landed, on attempt 64). The scored checkpoint is `ep2` from `sft/session.json` (`train_sft.py eval <checkpoint-path>`), because the run was lost at step 68/96. Tokenizer files in `sft/tokenizer/` are the public ones from huggingface.co/meta-models/Muse-Glimmer-30B.

## 7. Table, chart, business numbers
```
python3 compare.py            # quick table
python3 make_results.py       # markdown table with seeds grouped, spend line, misses of the best config
python3 chart.py              # frontier.png
```
