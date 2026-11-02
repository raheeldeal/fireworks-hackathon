# cypher/train status

Updated ~12:00 PT (after SFT).

Base: Muse Glimmer 30B (`accounts/fireworks/models/muse-glimmer-30b`), LoRA via Serverless Training API. SFT training free until 2026-11-30 (docs.fireworks.ai/fine-tuning/models.md, checked 11:50). No dataset upload, no deployment.
Locked test: 200 rows, sha256 6c47ee00...b491 (matches data/TEST_HASH). Leak check `check_leak.py data/test.jsonl data/train.jsonl`: 500 rows, 0 overlap.
Prompt (train = test): system = `prompts/v1_plain.txt` with the schema, user = question; ~760 prompt tokens per call. Sampler prefilled with ` to=user<|message|>` (reasoning off), same for every model.
Code: `train/rl.py` (eval / train / sample / build). Runs with `PYTHONPATH=train/.pylib ../runs/regex/venv311/bin/python` (neo4j driver installed into `train/.pylib`).
Training slot: all prior account sessions EXPIRED at 11:45, slot free.

| step | file | status |
|---|---|---|
| 1. base control | results/train_base.json | done: 48.5% acc (lenient 62.0%), err 2.0%, empty 4.0%; easy 34 / medium 59 / hard 51; 841 in / 49 out tok per call; $0.377 |
| 2. SFT (2 epochs, rank 16, lr 1e-4, batch 16) | results/train_sft.json | trained (64 steps, mean loss 0.65 -> ~0.15), scoring now |
| 3. RFT r1 / r2 | results/train_rft_r1.json, _r2.json | pending |

Spend: see `ledger.csv` (cap $6).

Sessions: SFT ts-d620b42267a34cda8302d76b0294fc03 DELETED right after save. Sampler `raheeldeal/run-58f25dda56b54a00b18f5fc7a630078e/cy-sft-3830a8d8`, training state `.../cy-sft-st`, promoted model `accounts/raheeldeal/models/cypher-sft-1150` (survives deletion; deployable per DEPLOY.md). Sampling a saved checkpoint needs no slot.
Data re-check before RFT sampling: test sha matches TEST_HASH; train.jsonl sha 63078173...f64f, 500 rows, 0 overlap.
