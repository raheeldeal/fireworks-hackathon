# product-json: messy product listing → strict JSON (Fireworks mock hackathon run, 2026-11-01)

**Result:** glm-5p3-flash with a rubric + 5-shot prompt reaches **95.5%** all-8-fields-correct (3 seeds 95.0–96.0%) at **$0.35/1k** and 1.4 s p50; the frontier kimi-k3 reaches 92.0% with the same rubric at $5.09/1k and 3.0 s. Full table, verdict and misses: [RESULTS.md](RESULTS.md). Chart: `frontier.png`. Pitch: [PITCH.md](PITCH.md). Business model: [BUSINESS.md](BUSINESS.md). Choices made overnight: [DECISIONS.md](DECISIONS.md).

## Layout
- `SPEC.md`, `schema.json`: task and the 8-field JSON schema (enums for product_type, color, material).
- `data/test.jsonl` (200 rows, LOCKED, sha256 `55fec063…`), `data/train.jsonl` (223 rows). Each row: `id, text, gold, noise`.
- `gen_data.py`: samples gold attributes (brands from `raw/esci_brands.json`, real Amazon ESCI brand strings), asks gpt-oss-120b to write the listing, regex-verifies every gold value is in the text. `split_data.py`: raw → test/train.
- `score.py`: scorer (JSON extraction guardrail, schema validation, normalised exact match). `python3 score.py` runs 7 unit tests.
- `fw.py`: Fireworks client with retries, price table and `ledger.csv`. `run_eval.py`: one model × one prompt → `results/<model>_<prompt>_s<seed>.json`. `route.py`: routing from existing result files. `compare.py`: markdown tables. `chart.py`: `frontier.png`.
- `prompts/`: `v1_plain.txt`, `v2_rubric.txt`, `v3_fewshot.txt` (built by `prompts/v3_fewshot_build.py` from train rows only).
- `ft/sft_muse.py`: free Muse Glimmer 30B LoRA SFT on the Serverless Training API + checkpoint sampling eval (phase 7). `ft/train_messages.jsonl`: Fireworks chat-format training file.
- `ledger.csv`: every paid call (timestamp, model, tokens, cost, note). `results/*.log`: run logs.

## Reproduce every number (from this folder; `source ~/.zshrc` sets FIREWORKS_API_KEY; Python 3.10, stdlib + matplotlib)
```bash
python3 score.py                                                   # scorer unit tests
python3 ../common/check_leak.py data/test.jsonl data/train.jsonl ft/train_messages.jsonl
shasum -a 256 data/test.jsonl                                      # 55fec063858774d3…
# baseline sweep (plain prompt). nemotron needs max_tokens 4000 for its reasoning.
python3 run_eval.py --model accounts/fireworks/models/nemotron-lightning-3p5-30b-a3b --prompt prompts/v1_plain.txt --max-tokens 4000
for m in glm-5p3-flash gpt-oss-120b deepseek-v4p1-flash glm-5p3; do python3 run_eval.py --model accounts/fireworks/models/$m --prompt prompts/v1_plain.txt; done
python3 run_eval.py --model accounts/fireworks/models/kimi-k3 --prompt prompts/v1_plain.txt --limit 100
# interventions
python3 run_eval.py --model accounts/fireworks/models/glm-5p3-flash --prompt prompts/v2_rubric.txt
python3 run_eval.py --model accounts/fireworks/models/glm-5p3-flash --prompt prompts/v2_rubric.txt --json-mode
python3 prompts/v3_fewshot_build.py && python3 run_eval.py --model accounts/fireworks/models/glm-5p3-flash --prompt prompts/v3_fewshot.txt
python3 run_eval.py --model accounts/fireworks/models/nemotron-lightning-3p5-30b-a3b --prompt prompts/v2_rubric.txt --max-tokens 4000
python3 run_eval.py --model accounts/fireworks/models/nemotron-lightning-3p5-30b-a3b --prompt prompts/v2_rubric.txt --json-mode --max-tokens 4000
python3 run_eval.py --model accounts/fireworks/models/kimi-k3 --prompt prompts/v2_rubric.txt --limit 100
# routing (no new calls)
python3 route.py results/glm-5p3-flash_v2_rubric_s7.json results/glm-5p3_v1_plain_s7.json --thresholds 1 2 3 --out results/route_glmflash-rubric_to_glm5p3_
python3 route.py results/glm-5p3-flash_v2_rubric_s7.json results/kimi-k3_v2_rubric_s7.json --thresholds 1 2 3 10 --out results/route_glmflash-rubric_to_kimi-rubric_
python3 route.py results/glm-5p3-flash_v3_fewshot_s7.json results/kimi-k3_v2_rubric_s7.json --thresholds 2 3 10 --out results/route_glmflash-fewshot_to_kimi-rubric_
# variance (seed = row order; temperature 0)
for s in 8 9; do python3 run_eval.py --model accounts/fireworks/models/glm-5p3-flash --prompt prompts/v1_plain.txt --seed $s; python3 run_eval.py --model accounts/fireworks/models/glm-5p3-flash --prompt prompts/v3_fewshot.txt --seed $s; done
python3 compare.py results/*.json && python3 chart.py
# phase 7: free Muse Glimmer LoRA SFT + sampler eval (Python 3.11 venv: ft/venv, `pip install "fireworks-ai[training]"`)
cd ft && ./venv/bin/python sft_muse.py --epochs 1 --base-limit 20 --tuned-limit 100
```
Data regeneration (`python3 gen_data.py --batches 112 --per 5 --out raw/gen_raw.jsonl; python3 split_data.py 200`) is temperature 0.9 and will not reproduce the locked test set byte for byte; the locked file is the reference.
