# train/ status (Worker C) — updated 2026-11-02 09:15 PT

Task: catalog-free tool routing on Muse Glimmer 30B, Serverless Training API (no dataset upload, no deployment).
Locked test set: 180 rows, sha256 bb50067286893483. Leak check: train_sft.jsonl, train.jsonl, data/rft_prompts.jsonl all 0 overlap.
Prompt at train and test: system "Reply with the single best tool name." + bare request. ~73 prompt tokens per call.

| step | result file | accuracy | invalid | out tok/call | p50 s | status |
|---|---|---|---|---|---|---|
| base, no catalog, no training | results/base_nocatalog.json | 0.0% | 180 | 29.2 | 0.84 | done |
| SFT LoRA (2 epochs, 40 steps, rank 8) | results/sft_nocatalog.json | 90.0% | 8 | 3.6 | 0.53 | done |
| RFT round 1 (rejection sampling) | results/rft_round1.json | | | | | sampling candidates |
| RFT round 2 | results/rft_round2.json | | | | | pending |

Stock reference (from the sweep, catalog in prompt): glm-5p3-flash 98.3% at ~1,700 prompt tokens.

Promoted model (survives session deletion, deployable per DEPLOY.md): `accounts/raheeldeal/models/tool-router-sft` (READY, HF_PEFT_ADDON).
Training sessions: ts-10713e9889ed49a697d6293bd5266e8e (SFT) — to be deleted after RFT round-1 candidates are sampled from it.
Spend so far: $0.115 of $3.00 (ledger.csv; sampler rates $1.96/M prefill, $4.88/M sample; training free).
Managed RFT: not available (uploads 403; docs mark managed RFT deprecated). rft_evaluator.py prepared, not run.
