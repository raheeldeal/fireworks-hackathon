# Function calling on Fireworks: mock hackathon run

Task: given a user request and OpenAI-format tool schemas, emit the one correct tool call (name + arguments). Data: BFCL v4 (simple_python, multiple, live_simple, live_multiple). Full spec in [SPEC.md](SPEC.md); every judgment call in [DECISIONS.md](DECISIONS.md); numbers in [RESULTS.md](RESULTS.md).

## Layout
| Path | What |
|---|---|
| `raw/` | BFCL v4 files as downloaded (questions + possible_answer) |
| `build_data.py` | raw → `data/test.jsonl` (200 rows, LOCKED, sha256 in `data/test.sha256`) and `data/train.jsonl` (394 rows) |
| `score.py` | deterministic scorer + output-parsing guardrail; `python3 score.py` runs its unit tests |
| `run_eval.py` | one model × one config → `results/<stem>.json`; appends to `ledger.csv`; refuses to run past the $3 cap |
| `route.py` | offline small→big routing sweep over confidence thresholds |
| `compare.py` | markdown table of all results (mean ± half-range over seeds) |
| `frontier.py` | `frontier.png` (accuracy vs. $/1k, log x) |
| `prep_sft.py`, `train_sft.py` | SFT file in Fireworks chat JSONL; serverless LoRA SFT on Muse Glimmer 30B + checkpoint scoring |
| `run_all.sh` | phases 4, 5, 5b (nemotron at max_tokens 4096 and with reasoning off), 6, 8 end to end (idempotent: skips existing results) |
| `run_renone.sh` | phase 5c: harness levers and 3 seeds on nemotron with `reasoning_effort: none` (called by `run_all.sh`) |
| `fix_cost.py` | backfills `total_cost_usd` in result files written before the short-model-name price fix (DECISIONS 12) |
| `wait_and_run.sh` | polls until the Fireworks account is unsuspended, then runs `run_all.sh` |
| `prompts/` | `v1_plain.txt` (baseline), `v2_rubric.txt` (rules written before seeing misses), `v3_misses.txt` (rules from the real baseline misses; measured worse) |
| `ledger.csv` | every paid run: tokens and cost at the PROTOCOL price table |

## Reproduce
```bash
cd hackathon/runs/function-calling
source ~/.zshrc                        # FIREWORKS_API_KEY
python3 score.py                       # unit tests
python3 ../common/check_leak.py data/test.jsonl data/train.jsonl data/sft_train.jsonl
./run_all.sh                           # baselines, interventions, routing, variance, chart (~$2.0 at the PROTOCOL prices)
python3 compare.py                     # the RESULTS.md table (routes collapsed to best + cheapest threshold; --all-routes for every threshold)
python3 frontier.py                    # frontier.png
```
Rebuilding the data (only if `data/test.jsonl` is absent; it refuses to overwrite the locked file):
```bash
python3 build_data.py && python3 prep_sft.py
```
Single run example:
```bash
python3 run_eval.py --model accounts/fireworks/models/nemotron-lightning-3p5-30b-a3b --mode tools --prompt prompts/v2_rubric.txt --logprobs
```
The winning configuration (RESULTS.md):
```bash
python3 run_eval.py --model accounts/fireworks/models/nemotron-lightning-3p5-30b-a3b --mode tools --reasoning-effort none --tool-choice required --logprobs
```
Fine-tuning (Python 3.11 venv in `.venv311`, SDK `fireworks-ai[training]`; Muse Glimmer 30B LoRA SFT is free on the Serverless Training API until 2026-11-30, evaluation sampling is paid per token and logged in `ledger.csv`):
```bash
.venv311/bin/python train_sft.py --epochs 1          # trains, saves a sampler checkpoint, scores base and tuned on data/test.jsonl
```

## Scoring in one paragraph
A prediction is parsed from `tool_calls` (tools mode) or from the text (json mode; fenced/wrapped/stringified JSON all accepted). It scores strict=1 when the name matches and every argument equals one of BFCL's acceptable values after normalization (lowercase keys, numeric equality, trimmed case-insensitive strings, ordered lists); arguments whose acceptable list contains `""` may be omitted; extra arguments fail. partial=0.5 for the right name with wrong arguments. Unparseable output counts as invalid (0).
