# cypher/train status

Updated 12:00 PT.

Base: Muse Glimmer 30B (`accounts/fireworks/models/muse-glimmer-30b`), LoRA via Serverless Training API. SFT training free until 2026-11-30 (docs.fireworks.ai/fine-tuning/models.md, checked 11:50). No dataset upload, no deployment.
Locked test: 200 rows, sha256 6c47ee00...b491 (matches data/TEST_HASH). Leak check `check_leak.py data/test.jsonl data/train.jsonl`: 500 rows, 0 overlap.
Prompt (train = test): system = `prompts/v1_plain.txt` with the schema, user = question; ~760 prompt tokens per call. Sampler prefilled with ` to=user<|message|>` (reasoning off), same for every model.
Code: `train/rl.py` (eval / train / sample / build). Runs with `PYTHONPATH=train/.pylib ../runs/regex/venv311/bin/python` (neo4j driver installed into `train/.pylib`).
Training slot: all prior account sessions EXPIRED at 11:45, slot free.

| step | file | status |
|---|---|---|
| 1. base control | results/train_base.json | running |
| 2. SFT (2 epochs, rank 16, lr 1e-4, batch 16) | results/train_sft.json | training |
| 3. RFT r1 / r2 | results/train_rft_r1.json, _r2.json | pending |

Spend: see `ledger.csv` (cap $6).
