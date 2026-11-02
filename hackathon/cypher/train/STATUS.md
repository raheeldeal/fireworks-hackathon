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
| 2. SFT (2 epochs, rank 16, lr 1e-4, batch 16) | results/train_sft.json | done: 56.5% (lenient 65.0%), err 0.5%, empty 1.0%; easy 49 / medium 61 / hard 60; 841 in / 44 out; $0.373. Pruned schema (results/train_sft_pruned.json): 54.5%, 668 in tok/call |
| 3. RFT r1 (advantage-weighted, cross_entropy with signed per-token weights; negative weights accepted) | results/train_rft_r1.json | candidates: 500x4 @0.8 from SFT, reward mean 0.569, 386/500 questions >=1 correct (202 mixed, 184 all-correct, 114 all-wrong) -> 808 weighted samples; training session ts-34fd72ca..., 51 steps lr 5e-5 |
| RFT r1 result | results/train_rft_r1.json | **32.5%** (lenient 38.0%), err 7.5%, empty 14.5%. Regression of 24 points vs SFT. The negative-weight updates pushed the model into one template (`WITH x ORDER BY .. LIMIT .. RETURN ..`) that often returns empty or invalid results. Session ts-34fd72ca... DELETED; model accounts/raheeldeal/models/cypher-r1-1201. |
| RFT r1, rejection sampling (fallback) | results/train_rft_r1_reject.json | training from SFT state on 386 reward-1 samples (shortest per question, same candidates, no new sampling cost), 1 epoch lr 5e-5 |
| RFT r2 | results/train_rft_r2.json | pending: reject variant again, new candidates from the r1-reject model on the 202 'mixed' questions (budget) |

Spend: see `ledger.csv` (cap $6).

Sessions: SFT ts-d620b42267a34cda8302d76b0294fc03 DELETED right after save. Sampler `raheeldeal/run-58f25dda56b54a00b18f5fc7a630078e/cy-sft-3830a8d8`, training state `.../cy-sft-st`, promoted model `accounts/raheeldeal/models/cypher-sft-1150` (survives deletion; deployable per DEPLOY.md). Sampling a saved checkpoint needs no slot.
Data re-check before RFT sampling: test sha matches TEST_HASH; train.jsonl sha 63078173...f64f, 500 rows, 0 overlap.

Incident: first r1 sampling run crashed at reward time (train rows have no `gold_result`; fixed by executing train gold once, cached in `train/data/train_gold.json`, 500/500 ok). Those samples (~$0.65) were lost; the script now writes `<out>.raw` before scoring. Ledger $3.64 after r1 sampling.

r2 sampling from the weighted r1 model was started and killed at 150/316 questions once r1 scored 32.5% (cost ~$0.14, wasted). Ledger $4.45 at 12:15.
