# meeting-actions: meeting transcript -> action items JSON

Everything in RESULTS.md is reproducible from this folder with the commands below (Python 3.10, stdlib + matplotlib; `source ~/.zshrc` for `FIREWORKS_API_KEY`). Every API call appends to `ledger.csv`; `scripts/fw.py` refuses new calls once the ledger reaches $3.00.

```bash
cd hackathon/runs/meeting-actions && source ~/.zshrc
python3 score.py                                   # scorer unit tests (5 cases)
python3 scripts/gen_data.py --n 400 --out data/all.jsonl   # gold-first synthetic transcripts (glm-5p3, resumable)
python3 scripts/split.py                           # train.jsonl = everything not in data/test_ids.json
python3 ../common/check_leak.py data/test.jsonl data/train.jsonl
shasum -a 256 data/test.jsonl                      # must print 6143b59c7fc675b7aa266e42428cd6a9a2ea231406c89d9e4dc6e2aa1d304cd4
```

**data/test.jsonl is locked.** Do not regenerate it; `gen_data.py` only appends ids that are missing from `data/all.jsonl`.

## Baselines and interventions (what produced results/*.json)
```bash
scripts/sweep.sh                                   # phase 4: six models, plain prompt (kimi on 70 rows)
python3 run_eval.py --model accounts/fireworks/models/glm-5p3-flash --prompt prompts/v2_rubric.txt
python3 run_eval.py --model accounts/fireworks/models/glm-5p3-flash --prompt prompts/v3_rubric_conf.txt
python3 run_eval.py --model accounts/fireworks/models/glm-5p3-flash --prompt prompts/v2_rubric.txt --json-mode
python3 scripts/fewshot.py && python3 run_eval.py --model accounts/fireworks/models/glm-5p3-flash --prompt prompts/v4_fewshot.txt
python3 run_eval.py --model accounts/fireworks/models/nemotron-lightning-3p5-30b-a3b --prompt prompts/v2_rubric.txt
python3 scripts/fill_missing.py results/<file>.json      # re-run rows dropped by transient errors
scripts/variance.sh accounts/fireworks/models/glm-5p3-flash prompts/v1_plain.txt    # seeds 1-3
python3 run_eval.py --model accounts/fireworks/models/glm-5p3-flash --prompt prompts/v4_fewshot.txt --seed 1   # and --seed 2
```
Per-model `reasoning_effort` settings live in `MODEL_EXTRA` in run_eval.py (see RESULTS.md gotchas).

## Offline analysis (no API calls)
```bash
python3 scripts/route.py results/glm-5p3-flash_v3_rubric_conf.json results/deepseek-v4p1-flash_v1_plain.json --thresholds 0.01 0.9 0.95
python3 scripts/route.py results/glm-5p3-flash_v3_rubric_conf.json results/deepseek-v4p1-flash_v1_plain.json --filter --thresholds 0.85 0.95
python3 scripts/rescore_all.py                     # re-score cached outputs after a scorer change
python3 scripts/rescore.py results/*_v1_plain.json # F1 at task-match thresholds 0.45 / 0.6 / 0.75
python3 scripts/misses.py results/glm-5p3-flash_v4_fewshot.json
python3 scripts/results_table.py                   # the RESULTS.md table
python3 scripts/business.py                        # the BUSINESS.md table
python3 scripts/chart.py                           # frontier.png
python3 compare.py results/*_v1_plain.json
```

## Fine-tuning (phase 7, not run)
Muse Glimmer 30B LoRA SFT is free until 2026-11-30 (docs.fireworks.ai/fine-tuning/models). Training data is ready: `python3 scripts/make_sft.py` -> `data/sft_train.jsonl` (247 rows, ~280k tokens; passes check_leak). The install step was not permitted in this session:
```bash
cd sft && ~/.pyenv/versions/3.11.9/bin/python3 -m venv .venv && source .venv/bin/activate
cd cookbook/training && pip install -e .           # cookbook already cloned in sft/cookbook
python -m examples.sft.muse_glimmer_starter plan --surface serverless      # must show training "$0 (promotional)"
python -m examples.sft.muse_glimmer_starter prepare --file ../../../data/sft_train.jsonl --run-id ma-$(date +%H%M)
python -m examples.sft.muse_glimmer_starter launch --surface serverless --file ../../../data/sft_train.jsonl --run-id <same>
```
Scoring the tuned adapter must use the Training SDK sampler (serverless checkpoints), never a dedicated deployment.

## Layout
`SPEC.md` task and scoring · `DECISIONS.md` every judgment call with timestamps · `RESULTS.md` the numbers · `BUSINESS.md` · `PITCH.md` · `frontier.png` · `data/` · `prompts/` · `results/` (one JSON per run, per-row raw outputs included) · `scripts/` · `ledger.csv`
