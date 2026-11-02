# Banking intent routing (Banking77, 77 classes): reproduce every number in RESULTS.md

Everything runs from this folder with Python 3.10 (stdlib + matplotlib) except the SFT step (Python 3.11 venv in `sft/`).
```bash
cd hackathon/runs/intent-routing
source ~/.zshrc            # FIREWORKS_API_KEY
```

## 1. Data (locked; rebuilding reproduces the same hash)
```bash
python3 -I build_data.py                                   # data/test.jsonl (154) + data/train.jsonl (308), seed 20261101
python3 -I ../common/check_leak.py data/test.jsonl data/train.jsonl data/sft_train.jsonl
shasum -a 256 data/test.jsonl                              # 3547e8f9bc1491ce...
python3 -I make_prompts.py                                 # prompts/v1_plain v2_conf v3_rubric v4_fewshot (from labels.json)
python3 -I make_sft_data.py                                # data/sft_train.jsonl + prompts/v0_sft_short.txt
python3 -I score.py                                        # 8/8 scorer unit tests
```

## 2. Every model run (phases 4 to 6)
`run_eval.py` writes `results/<model>_<prompt>[_json][_<effort>][_s<seed>][_n<limit>].json` and appends every call to `ledger.csv`; it stops itself at the $3 cap. Rows that fail with 429/5xx are stored with `error` set; `python3 retry_all.py` re-runs only those rows and merges them in place.
```bash
./resume.sh                 # the exact sequence used tonight (phases 4-8), ~25 min with 3 workers per run
python3 retry_all.py        # until "remaining errored rows: 0"
python3 run_eval.py --model accounts/fireworks/models/glm-5p3-flash --prompt prompts/v3_rubric.txt --workers 2   # the one extra run
```
Single-run form: `python3 run_eval.py --model <id> --prompt prompts/<p>.txt [--effort none|low] [--json-mode] [--seed N] [--limit 100]`.

## 3. Routing sweeps (offline, exact at temperature 0)
```bash
python3 routing_sim.py results/glm-5p3-flash_v2_conf_low.json results/kimi-k3_v1_plain_n100.json --out results/routing_glm-5p3-flash_v2_conf_low__kimi-k3.json
```
Repeat for any (small, big) pair; `resume.sh` phase 5d and the commands in DECISIONS.md generated the 27 files in `results/routing_*.json`.

## 4. Tables, calibration, misses, spend
```bash
python3 -I summarize.py glm-5p3-flash_v1_plain          # prints the RESULTS.md tables and the misses list
```

## 5. Chart
```bash
python3 make_chart.py --best results/glm-5p3-flash_v1_plain.json --routes routing_glm-5p3-flash_v2_conf_low__kimi-k3,routing_glm-5p3-flash_v2_conf_low__gpt-oss,routing_glm-5p3-flash_v2_conf__kimi-k3
```

## 6. Free SFT (phase 7; serverless training API, never a deployment)
```bash
sft/venv/bin/python sft_muse.py plan     # offline cost check: training $0 (promo to 2026-11-30), eval ≈ $0.03
sft/venv/bin/python sft_muse.py train    # LoRA rank 8, 1 epoch, batch 16, lr 1e-4 → sft/run.json (run id, checkpoint path)
sft/venv/bin/python sft_muse.py eval     # samples the 154 test rows from the checkpoint → results/muse-glimmer-30b_sft.json
```
Venv setup if missing: `~/.pyenv/versions/3.11.9/bin/python -m venv sft/venv && sft/venv/bin/pip install "fireworks-ai[training]" numpy orjson transformers jinja2 tokenizers huggingface_hub`.
Account limit: one concurrent serverless training run per base model; `train` fails fast with 429 while another run is active.

## Files
- SPEC.md, DECISIONS.md, RESULTS.md, BUSINESS.md, PITCH.md, frontier.png
- labels.json (77 one-line definitions), score.py, run_eval.py, routing_sim.py, summarize.py, make_chart.py, retry_all.py, resume.sh, poll_api.sh
- data/ (test.jsonl locked chmod 444, train.jsonl, sft_train.jsonl, test.sha256, leak_check.txt), prompts/, results/ (one JSON per run with every row), ledger.csv
