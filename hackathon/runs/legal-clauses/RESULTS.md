# legal-clauses (LEDGAR, 100-class contract clause classification)
Status: complete (all 11 phases; the phase 7 fine-tune ran 68 of 96 planned steps: the serverless training run was lost with HTTP 404 at step 68 after two full epochs had been saved, so the epoch-2 checkpoint (64 steps) is the one scored)
Test set: 199 rows, sha256 08f0ae5dc704e13b6207572c5acdf80d40316d82a192a34fff2268f283cd410f, source https://huggingface.co/datasets/coastalcph/lex_glue (config ledgar, official test split, 2 per class; 1 class has only 1 eligible row)
Leak check:
```
test set: 199 rows, sha256 08f0ae5dc704e13b
data/train.jsonl: 500 rows, 0 overlap with test
sft/train_chat.jsonl: 500 rows, 0 overlap with test
```
Spend: $2.32 inference, $0.00 training (free Muse Glimmer promotion), $0.19 tuned-model sampling = $2.51 of $3.00 (from ledger.csv, 3,697 calls)

Scoring: exact label match after normalization (accuracy), macro-F1 over the 100 classes; outputs not in the label set are `invalid` and score 0. All runs temperature 0, max_tokens 2048, thinking disabled where the model allows it (`chat_template_kwargs.enable_thinking=false`: nemotron, deepseek, kimi) or `reasoning_effort=low` (GLM 5.3, GLM 5.3 Flash, gpt-oss-120b, which reject the switch). "nothink" in a config name marks that; `v1_plain` without it on nemotron is the thinking run.

## Results table
| config | model | n | accuracy | macro-F1 | invalid | p50 s | p95 s | $/1k | seeds |
|---|---|---|---|---|---|---|---|---|---|
| v1_plain nothink80 | kimi-k3 | 80 | 73.8% | 68.5% | 0 | 1.03 | 3.58 | 7.244 | 1 |
| routing t0.95 | route(nemotron-lightning-3p5-30b-a3b->deepseek-v4p1-flash) | 199 | 69.3% | 64.9% | 1 | 0.82 | 1.55 | 0.606 | 1 |
| v4_json nothink | glm-5p3-flash | 199 | 68.8% ± 0.5% | 64.6% ± 0.6% | 0 | 0.58 ± 0.01 | 1.05 ± 0.13 | 0.363 | 3 |
| v1_plain nothink | deepseek-v4p1-flash | 199 | 68.8% | 64.5% | 1 | 0.66 | 1.20 | 0.704 | 1 |
| routing t0.7 | route(glm-5p3-flash->deepseek-v4p1-flash) | 199 | 68.8% | 65.0% | 1 | 0.93 | 1.87 | 0.702 | 1 |
| routing t0.99 | route(glm-5p3-flash->deepseek-v4p1-flash) | 199 | 68.8% | 64.5% | 1 | 1.28 | 2.10 | 1.045 | 1 |
| routing t0.95 | route(glm-5p3-flash->deepseek-v4p1-flash) | 199 | 68.3% | 63.9% | 1 | 1.22 | 2.00 | 0.956 | 1 |
| routing t0.9 | route(nemotron-lightning-3p5-30b-a3b->deepseek-v4p1-flash) | 199 | 68.3% | 63.7% | 1 | 0.79 | 1.48 | 0.546 | 1 |
| routing t0.99 | route(nemotron-lightning-3p5-30b-a3b->deepseek-v4p1-flash) | 199 | 68.3% | 63.7% | 1 | 0.92 | 1.90 | 0.772 | 1 |
| routing t0.5 | route(glm-5p3-flash->deepseek-v4p1-flash) | 199 | 67.8% | 63.7% | 0 | 0.62 | 1.75 | 0.517 | 1 |
| routing t0.9 | route(glm-5p3-flash->deepseek-v4p1-flash) | 199 | 67.8% | 63.4% | 1 | 1.18 | 2.00 | 0.889 | 1 |
| routing t0.5 | route(glm-5p3-flash->glm-5p3) | 199 | 67.3% | 63.2% | 0 | 0.62 | 1.51 | 1.108 | 1 |
| v1_plain | glm-5p3-flash | 199 | 66.8% ± 0.5% | 63.2% ± 0.6% | 0 | 0.54 ± 0.04 | 1.05 ± 0.05 | 0.358 | 3 |
| v3_fewshot nothink | glm-5p3-flash | 199 | 66.8% | 62.9% | 0 | 0.56 | 0.98 | 0.426 | 1 |
| routing t0.7 | route(glm-5p3-flash->glm-5p3) | 199 | 66.8% | 62.0% | 0 | 0.94 | 1.64 | 1.974 | 1 |
| v1_plain nothink | glm-5p3 | 199 | 66.3% | 61.2% | 0 | 0.55 | 0.88 | 3.315 | 1 |
| routing t0.9 | route(glm-5p3-flash->glm-5p3) | 199 | 66.3% | 61.2% | 0 | 1.11 | 1.66 | 2.857 | 1 |
| routing t0.95 | route(glm-5p3-flash->glm-5p3) | 199 | 66.3% | 61.2% | 0 | 1.15 | 1.74 | 3.174 | 1 |
| routing t0.99 | route(glm-5p3-flash->glm-5p3) | 199 | 66.3% | 61.2% | 0 | 1.18 | 1.74 | 3.590 | 1 |
| routing t0.9 | route(nemotron-lightning-3p5-30b-a3b->glm-5p3) | 199 | 65.8% | 60.7% | 0 | 0.74 | 1.24 | 2.107 | 1 |
| routing t0.95 | route(nemotron-lightning-3p5-30b-a3b->glm-5p3) | 199 | 65.8% | 60.6% | 0 | 0.76 | 1.39 | 2.390 | 1 |
| routing t0.99 | route(nemotron-lightning-3p5-30b-a3b->glm-5p3) | 199 | 65.8% | 60.7% | 0 | 0.80 | 1.54 | 3.173 | 1 |
| routing t0.7 | route(nemotron-lightning-3p5-30b-a3b->deepseek-v4p1-flash) | 199 | 63.8% | 58.5% | 1 | 0.37 | 1.41 | 0.386 | 1 |
| v2_rubric nothink | glm-5p3-flash | 199 | 63.3% | 59.6% | 0 | 0.61 | 1.21 | 0.536 | 1 |
| routing t0.7 | route(nemotron-lightning-3p5-30b-a3b->glm-5p3) | 199 | 62.8% | 57.3% | 0 | 0.37 | 1.22 | 1.357 | 1 |
| routing t0.5 | route(nemotron-lightning-3p5-30b-a3b->deepseek-v4p1-flash) | 199 | 61.3% | 55.4% | 1 | 0.29 | 1.26 | 0.241 | 1 |
| routing t0.5 | route(nemotron-lightning-3p5-30b-a3b->glm-5p3) | 199 | 60.8% | 54.9% | 0 | 0.29 | 1.11 | 0.674 | 1 |
| v3_fewshot nothink | nemotron-lightning-3p5-30b-a3b | 199 | 59.8% | 54.3% | 0 | 0.29 | 1.74 | 0.149 | 1 |
| v1_plain | gpt-oss-120b | 199 | 57.8% | 52.3% | 0 | 0.36 | 0.69 | 0.378 | 1 |
| v1_plain nothink | nemotron-lightning-3p5-30b-a3b | 199 | 56.8% | 51.1% | 1 | 0.24 | 0.90 | 0.125 | 1 |
| v2_rubric nothink | nemotron-lightning-3p5-30b-a3b | 199 | 56.3% | 51.8% | 5 | 0.28 | 1.51 | 0.187 | 1 |
| v4_json nothink | nemotron-lightning-3p5-30b-a3b | 199 | 55.8% | 50.0% | 1 | 0.31 | 1.65 | 0.126 | 1 |
| v1_plain | nemotron-lightning-3p5-30b-a3b | 199 | 33.2% | 33.1% | 104 | 4.97 | 7.08 | 0.458 | 1 |

Routing rows are simulations from the two models' own result files (escalate when the small model's answer is invalid or its first-token probability is below the threshold); cost counts both calls for escalated rows.

Seeds: the `v1_plain` and `v4_json nothink` rows for glm-5p3-flash are 3 seeds (7, 11, 13; shuffled row order). Plain: 66.8 / 67.3 / 66.3 = 66.8% ± 0.5. JSON mode: 69.3 / 68.3 / 68.8 = 68.8% ± 0.5.

| config | model | accuracy | invalid | p50 s | p95 s | $/1k | seeds |
|---|---|---|---|---|---|---|---|
| LoRA SFT, short prompt (phase 7) | muse-glimmer-30b-lora (rank 8, 2 epochs, 500 rows) | 68.8% (macro-F1 64.7) | 0 | 0.66 | 2.37 | 0.959 (eval-path sampling meter) | 1 |

## Best small-model result vs. frontier
The best small configuration, glm-5p3-flash with JSON-mode output and no thinking, scores 68.8% ± 0.5 (3 seeds) at $0.36 per 1k requests and 0.58 s p50; the frontier model kimi-k3 scores 73.8% on an 80-row subset at $7.24 per 1k and 1.03 s p50. On those same 80 rows glm-5p3-flash JSON scores 76.2% and the large glm-5p3 75.0%, so the frontier model is not measurably better than a 20x cheaper small model on this task.

## Headroom verdict
No: this task is not a frontier-struggles pick. Every configuration lands between 57% and 74%, prompting adds at most 2 points (JSON mode), a 25-rule rubric and 5-shot examples do not help, routing cannot exceed the best single small model (69.3%), and the fine-tune did not move the ceiling either: Muse Glimmer 30B LoRA on 500 labeled clauses (5 per class, train loss 2.5 -> 0.07) scores exactly the same 68.8% as glm-5p3-flash JSON mode, with 0 invalid outputs and a 330-token prompt instead of 2,700. It misses 62 rows, glm-flash 61, and 44 of those are the same rows: near-synonym headings (Indemnifications vs Indemnity, Costs vs Expenses, Entire Agreements vs Integration, Representations vs Warranties, Binding Effects vs Effectiveness) where the gold label is a convention of the source contract that five examples per class cannot teach. The frontier model is not better than the small ones on matched rows (kimi-k3 73.8% vs glm-flash 76.2% on the same 80 clauses), so the gap to fill is label noise, not model capability. What the fine-tune does buy is the cheapest possible request shape (no label list, 5-token answer, no thinking); its $/1k here is the serverless-training sampling meter, not a serving price. I would not pick this task as framed; with a coarser label set (LEDGAR's 100 headings collapsed to ~30 provision types) or 50+ examples per class it may clear 80%, but that is a different dataset.

## Misses analysis (best config: glm-5p3-flash + JSON mode, seed 7, 61 misses of 199)
1. gold **Assigns** -> **Successors** (2x): "binding upon and inure to the benefit of ... their respective successors and assigns". The clause text is identical to a Successors clause; only the contract's heading differs. Hypothesis: label noise that only a model trained on LEDGAR's heading habits can reproduce.
2. gold **Consent To Jurisdiction** -> **Submission To Jurisdiction** (2x): clause literally says "irrevocably submits to the jurisdiction". The model followed the words; the heading said "Consent". Same hypothesis.
3. gold **Applicable Laws** -> **Governing Laws** (2x): "interpreted under the laws of the state of Minnesota". A governing-law clause by content; the gold label reflects the heading "Applicable Law". Hypothesis: dataset convention.
4. gold **Authorizations** -> **Authority** (2x): "taken all appropriate corporate action to authorize". Genuinely ambiguous between the two labels; definitions overlap.
5. gold **Costs** -> **Expenses**: "The Company shall bear all expenses associated with administering the Plan". The clause says "expenses"; heading said "Costs". Dataset convention.
6. gold **Qualifications** -> **Existence**: "duly organized, validly existing and in good standing ... and qualified to do business". Multi-topic clause; the model picked the first topic. Hypothesis: for compound clauses the heading names the last or most specific topic; a trained model learns that.
7. gold **Expenses** -> **Death**: a clause about the personal representative of a deceased grantee exercising an option. Model keyed on "death"; gold is about who bears the expenses. Reasonable error.
8. gold **Insurances** -> **Closings**: "The Administrative Agent shall have received insurance certificates": a closing condition about insurance. Ambiguous; either label is defensible.
9. gold **Binding Effects** -> **Effectiveness**: "shall not be valid and binding ... unless and until executed". Both labels plausible; the heading was "Binding Effect".
10. gold **Agreements** -> **Entire Agreements**: a textbook entire-agreement clause labeled "Agreements" (its heading was probably "Agreement"). Pure label noise.

Pattern: roughly half of the misses are pairs of near-synonym headings where the gold label is a convention of the source contract. A prompt cannot encode conventions; examples can. That is the headroom.

## Gotchas hit tonight
- 22:04 Fireworks account suspended (HTTP 412 PRECONDITION_FAILED, monthly spending limit) on the first smoke call; cleared at ~22:16 after the owner raised it. Built a probe-and-resume driver meanwhile.
- `reasoning_effort=low` does not stop nemotron-lightning thinking: 600 to 2,048 reasoning tokens per call, half the answers truncated -> 33.2% with 104 invalid. Fix: `chat_template_kwargs: {"enable_thinking": false}` (4 output tokens, 56.8%). GLM 5.3 / Flash and gpt-oss-120b reject that switch with HTTP 400 ("thinking-only model"); harness falls back to `reasoning_effort=low` (0 to 10 reasoning tokens).
- Rate limits: HTTP 429 on roughly a third of calls with ten agents sharing the account; 8 retries with backoff capped at 30 s, plus `fix_errors.py` to re-run rows that still failed (2 to 18 rows per run). All reported runs have 0 error rows.
- The app relaunched my first background driver, so two copies ran; `pkill` was denied by the permission classifier. Fix: atomic per-output lock dirs in run_eval.py; pre-made lock dirs fence off configs I wanted to run manually.
- HF datasets-server `/filter` returned auth errors; used the public parquet files with pyarrow in a venv.
- LEDGAR class `Books` has 1 clause of 20 to 250 words in the test and validation splits; test set is 199 rows.
- Logprob confidence: in JSON mode the first token is `{`, so confidence is meaningless; routing used the plain-prompt runs. nemotron's confidence is usefully calibrated (21% accuracy below 0.5, 78% at 0.9 to 0.99).
- Fine-tuning: cookbook clone denied (external code); wrote the LoRA loop against the PyPI SDK. Serverless training allows one concurrent run per base model per account; siblings held the slot from 22:26 until 02:53 (36 five-minute retries all failed; a 60-second poller got it on attempt 64). The run then died at step 68/96 with HTTP 404 `retrieve_future: session or run not found` while the session itself stayed READY; the epoch-2 sampler checkpoint saved at step 64 was scored instead (199 rows, $0.19). Training was free (no training line on the ledger; Muse Glimmer promotion per docs.fireworks.ai/fine-tuning/models.md). Session deleted after scoring.
