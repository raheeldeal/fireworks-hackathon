# code-fix: mock hackathon run

Task: given a buggy Python function and the failing unit-test output, return the corrected function. Scored by
running the hidden HumanEvalFix test suite in a sandboxed subprocess. Details in `SPEC.md`; every decision in
`DECISIONS.md`; numbers in `RESULTS.md`; chart in `frontier.png`; pitch in `PITCH.md`; money in `BUSINESS.md`.

## Files
| file | purpose |
|---|---|
| `data/test.jsonl` | locked test set, 164 rows (HumanEvalFix python). Never modified after creation. |
| `data/train.jsonl` | 300 rows, MBPP + rule-based AST bug injection (few-shot pool; SFT file if budget existed) |
| `build_data.py` | rebuilds both files from the raw downloads (refuses to overwrite test.jsonl) |
| `sandbox.py` | runs untrusted code: subprocess, `python3 -I`, `sandbox-exec` deny-network, 10 s timeout |
| `score.py` | extracts the function from model output, runs hidden tests; `python3 score.py` runs 6 unit tests |
| `run_eval.py` | one model × one prompt over the test set; writes `results/*.json`; appends `ledger.csv` |
| `route.py` | offline routing small→large from two results files (verify / self-confidence / token signals) |
| `variance.py` | mean ± range over seed runs |
| `chart.py` | `frontier.png` |
| `compare.py` | table (`--md` for RESULTS.md) |
| `sweep.sh` | the whole protocol, idempotent (skips finished stages) |
| `patch_rows.py` | re-runs only rows that failed for infrastructure reasons (429 after retries, reasoning hit max_tokens) → `*_retry.json` |
| `wait_and_run.sh` | polls the API every 5 min and runs `sweep.sh` when the account is un-suspended |
| `ledger.csv` | every paid call: timestamp, model, tokens, cost |

## Reproduce everything
```bash
source ~/.zshrc            # FIREWORKS_API_KEY
cd hackathon/runs/code-fix
python3 score.py           # scorer unit tests (6 cases, one must score 0, two must be invalid)
python3 ../common/check_leak.py data/test.jsonl data/train.jsonl   # hash + leak check
bash sweep.sh              # baselines, interventions, routing, variance, chart (~$1.45 as run)
python3 patch_rows.py results/*_v1_plain.json results/glm-5p3-flash_v*.json results/kimi-k3_v1_plain_n100.json   # clean pass (~$0.5)
bash finalize.sh           # routes, variance, chart, tables from the *_retry.json files (no API calls)
python3 compare.py --md results/*_retry*.json   # clean table
```
Individual runs:
```bash
python3 run_eval.py --model accounts/fireworks/models/glm-5p3-flash --prompt prompts/v1_plain.txt
python3 run_eval.py --model accounts/fireworks/models/glm-5p3-flash --prompt prompts/v2_rubric.txt
python3 run_eval.py --model accounts/fireworks/models/glm-5p3-flash --prompt prompts/v1_plain.txt --shots 5
python3 run_eval.py --model accounts/fireworks/models/glm-5p3-flash --prompt prompts/v1_plain.txt --json
python3 run_eval.py --model accounts/fireworks/models/glm-5p3-flash --prompt prompts/v1_plain.txt --confidence
python3 run_eval.py --model accounts/fireworks/models/kimi-k3 --prompt prompts/v1_plain.txt --limit 100 --workers 2
python3 route.py --small results/glm-5p3-flash_v1_plain.json --large results/glm-5p3_v1_plain.json --signal verify
python3 run_eval.py --model accounts/fireworks/models/glm-5p3-flash --prompt prompts/v1_plain.txt --seed 1
python3 chart.py
```
Re-scoring an existing results file without new API calls (e.g. to audit the sandbox):
```bash
python3 -c "import json,score; d=json.load(open('results/glm-5p3-flash_v1_plain.json')); t={json.loads(l)['id']:json.loads(l) for l in open('data/test.jsonl')}; print(sum(score.score(r['raw'],t[r['id']])['correct'] for r in d['rows'])/d['n'])"
```

## Rebuilding the data from scratch
```bash
RAW=/path/to/raw && mkdir -p $RAW
# HumanEvalFix: https://datasets-server.huggingface.co/rows?dataset=bigcode%2Fhumanevalpack&config=python&split=test&offset=0&length=100  (and offset=100) -> merge the `row` objects into $RAW/rows.jsonl
curl -sL -o $RAW/sanitized-mbpp.json https://raw.githubusercontent.com/google-research/google-research/master/mbpp/sanitized-mbpp.json
python3 build_data.py --raw $RAW --n-train 300
```
