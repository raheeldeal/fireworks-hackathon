# Phase 7 commands (NOT run tonight; see DECISIONS.md item 9)
Free LoRA SFT on Muse Glimmer 30B via the Serverless Training API (free until 2026-11-30 per fireworks.ai/pricing),
scored by serverless checkpoint sampling (no dedicated deployment).

```bash
cd hackathon/runs/code-fix
pyenv install -s 3.11.9 && ~/.pyenv/versions/3.11.9/bin/python -m venv sft/.venv && source sft/.venv/bin/activate
git clone --depth 1 https://github.com/fw-ai/cookbook.git sft/cookbook && pip install -e sft/cookbook/training
export FIREWORKS_API_KEY=...   # must be an un-suspended account
python3 ../common/check_leak.py data/test.jsonl data/train_messages.jsonl   # must print 0 overlap
# Before launching: open the job creation page / dry run and confirm the shown price is $0. Abort otherwise (protocol rule 4).
python sft/cookbook/training/examples/muse_glimmer_sft.py --dataset data/train_messages.jsonl --epochs 2 --lora-rank 16
# then: save_weights_for_sampler("final") -> create_sampling_client(model_path) -> sample each test row's messages at
# temperature 0 -> score.score(raw, row). Sampling tokens are billed at serverless rates: log them in ledger.csv.
```
Expected training tokens ≈ 160k × 2 epochs (under the 300k single-epoch guidance). If the promotion is gone, do NOT run.
