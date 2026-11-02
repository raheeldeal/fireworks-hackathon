# function-calling
Status: complete (phases 1 to 11; every planned row measured, SFT trained and scored)
Test set: 200 rows, sha256 a9ef43af57e1e883280280658f40ac00accc9ae9d35d25e2d0e54ee723912fa7, source https://github.com/ShishirPatil/gorilla/tree/main/berkeley-function-call-leaderboard/bfcl_eval/data (BFCL v4 simple_python 40, multiple 50, live_simple 40, live_multiple 70; Apache-2.0)
Leak check:
```
test set: 200 rows, sha256 a9ef43af57e1e883
data/train.jsonl: 394 rows, 0 overlap with test
test set: 200 rows, sha256 a9ef43af57e1e883
data/sft_train.jsonl: 394 rows, 0 overlap with test
```
Spend: $2.46 inference (of which $0.00 is Muse Glimmer sampler evaluation at the serverless-training rates), $0.00 training (Muse Glimmer LoRA SFT is free until 2026-11-30; from ledger.csv; total $2.46 of the $3.00 cap)

## Results table
Strict = right function and every argument right (BFCL acceptable-value sets); partial = 0.5 for right function wrong arguments. $/1k from token counts × the PROTOCOL price table, so hidden reasoning tokens are included. Seeds: mean ± half-range. Route rows: offline escalation from the per-row results (best-accuracy and cheapest threshold per pair; `python3 compare.py --all-routes` for every threshold). Suffixes: `mt4096` = max_tokens 4096 (default 1024), `renone` = `reasoning_effort: none`, `relow` = `reasoning_effort: low`, `required` = `tool_choice: required`.

| config | model | n | strict acc | partial | invalid | p50 s | p95 s | $/1k | seeds |
|---|---|---|---|---|---|---|---|---|---|
| glm-5p3_json_v1_plain_relow | glm-5p3 | 100 | 92.0% | 95.0% | 2 | 0.69 | 0.98 | 0.862 | 1 |
| glm-5p3-flash_tools_v1_plain | glm-5p3-flash | 200 | 91.5% | 95.0% | 1 | 0.93 | 1.91 | 0.151 | 1 |
| route_glm-5p3-flash_tools_v1_plain_to_glm-5p3_tools_v1_plain_relow:invalid-only (esc 0%) | route:glm-5p3-flash->glm-5p3 | 200 | 91.5% | 95.0% | 0 | 0.93 | 1.96 | 0.157 | 1 |
| route_nemotron-lightning-3p5-30b-a3b_tools_v1_plain_renone_to_glm-5p3-flash_tools_v1_plain:-0.01 (esc 31%) | route:nemotron-lightning-3p5-30b-a3b->glm-5p3-flash | 200 | 91.5% | 94.8% | 0 | 0.47 | 2.12 | 0.102 | 1 |
| nemotron-lightning-3p5-30b-a3b_tools_v1_plain_required_renone | nemotron-lightning-3p5-30b-a3b | 200 | 91.0% ± 0.5% | 95.2% | 0 | 0.39 | 1.46 | 0.054 | 4 |
| route_nemotron-lightning-3p5-30b-a3b_tools_v1_plain_required_renone_to_glm-5p3-flash_tools_v1_plain:invalid-only (esc 0%) | route:nemotron-lightning-3p5-30b-a3b->glm-5p3-flash | 200 | 91.0% | 95.2% | 0 | 0.40 | 1.90 | 0.054 | 1 |
| gpt-oss-120b_json_v1_plain | gpt-oss-120b | 200 | 90.5% | 93.8% | 4 | 0.65 | 1.53 | 0.162 | 1 |
| deepseek-v4p1-flash_json_v1_plain | deepseek-v4p1-flash | 200 | 90.0% | 93.8% | 5 | 1.26 | 4.09 | 0.289 | 1 |
| glm-5p3_tools_v1_plain_relow | glm-5p3 | 200 | 90.0% | 93.5% | 3 | 0.67 | 0.92 | 1.058 | 1 |
| route_nemotron-lightning-3p5-30b-a3b_tools_v1_plain_mt4096_to_glm-5p3-flash_tools_v1_plain:-0.01 (esc 13%) | route:nemotron-lightning-3p5-30b-a3b->glm-5p3-flash | 200 | 90.0% | 94.2% | 0 | 2.20 | 8.25 | 0.218 | 1 |
| glm-5p3-flash_json_v1_plain | glm-5p3-flash | 200 | 89.5% | 92.8% | 6 | 0.99 | 2.49 | 0.145 | 1 |
| route_nemotron-lightning-3p5-30b-a3b_tools_v1_plain_to_glm-5p3-flash_tools_v1_plain:-0.02 (esc 22%) | route:nemotron-lightning-3p5-30b-a3b->glm-5p3-flash | 200 | 89.5% | 94.0% | 0 | 1.62 | 5.15 | 0.183 | 1 |
| sft_muse-glimmer-30b_tuned_json_v1_plain | muse-glimmer-30b#lora-sft-tuned | 200 | 89.5% | 94.2% | 1 | 0.00 | 2.60 | 1.321 | 1 |
| nemotron-lightning-3p5-30b-a3b_json_v1_plain_mt4096 | nemotron-lightning-3p5-30b-a3b | 200 | 89.2% ± 0.8% | 93.6% | 2 | 1.64 | 4.95 | 0.156 | 4 |
| nemotron-lightning-3p5-30b-a3b_json_v1_plain_renone | nemotron-lightning-3p5-30b-a3b | 200 | 89.0% | 94.2% | 0 | 0.34 | 1.20 | 0.037 | 1 |
| route_nemotron-lightning-3p5-30b-a3b_tools_v1_plain_mt4096_to_glm-5p3-flash_tools_v1_plain:invalid-only (esc 2%) | route:nemotron-lightning-3p5-30b-a3b->glm-5p3-flash | 200 | 89.0% | 93.8% | 0 | 2.16 | 8.25 | 0.202 | 1 |
| route_nemotron-lightning-3p5-30b-a3b_tools_v1_plain_renone_to_glm-5p3-flash_tools_v1_plain:invalid-only (esc 2%) | route:nemotron-lightning-3p5-30b-a3b->glm-5p3-flash | 200 | 89.0% | 94.2% | 0 | 0.38 | 1.34 | 0.058 | 1 |
| route_nemotron-lightning-3p5-30b-a3b_tools_v1_plain_to_glm-5p3-flash_tools_v1_plain:invalid-only (esc 21%) | route:nemotron-lightning-3p5-30b-a3b->glm-5p3-flash | 200 | 88.5% | 93.5% | 0 | 1.62 | 5.09 | 0.182 | 1 |
| route_nemotron-lightning-3p5-30b-a3b_tools_v1_plain_to_glm-5p3_tools_v1_plain_relow:-0.02 (esc 22%) | route:nemotron-lightning-3p5-30b-a3b->glm-5p3 | 200 | 88.5% | 93.0% | 0 | 1.59 | 4.28 | 0.383 | 1 |
| deepseek-v4p1-flash_tools_v1_plain | deepseek-v4p1-flash | 200 | 88.0% | 91.8% | 8 | 1.11 | 2.42 | 0.358 | 1 |
| kimi-k3_tools_v1_plain | kimi-k3 | 100 | 88.0% | 93.5% | 1 | 1.85 | 4.62 | 3.158 | 1 |
| nemotron-lightning-3p5-30b-a3b_tools_v1_plain_mt4096 | nemotron-lightning-3p5-30b-a3b | 200 | 88.0% | 92.8% | 4 | 2.15 | 8.25 | 0.199 | 1 |
| nemotron-lightning-3p5-30b-a3b_tools_v2_rubric_mt4096 | nemotron-lightning-3p5-30b-a3b | 200 | 88.0% | 93.2% | 2 | 2.36 | 7.94 | 0.233 | 1 |
| route_nemotron-lightning-3p5-30b-a3b_tools_v1_plain_to_glm-5p3_tools_v1_plain_relow:invalid-only (esc 21%) | route:nemotron-lightning-3p5-30b-a3b->glm-5p3 | 200 | 87.5% | 92.5% | 0 | 1.59 | 4.25 | 0.372 | 1 |
| nemotron-lightning-3p5-30b-a3b_tools_v1_plain_mt4096_relow | nemotron-lightning-3p5-30b-a3b | 200 | 86.5% | 91.5% | 5 | 2.11 | 9.02 | 0.208 | 1 |
| nemotron-lightning-3p5-30b-a3b_tools_v2_rubric_renone | nemotron-lightning-3p5-30b-a3b | 200 | 86.5% | 93.0% | 0 | 0.38 | 1.42 | 0.066 | 1 |
| nemotron-lightning-3p5-30b-a3b_tools_v1_plain_renone | nemotron-lightning-3p5-30b-a3b | 200 | 86.2% ± 0.5% | 91.7% | 5 | 0.39 | 1.58 | 0.055 | 4 |
| gpt-oss-120b_tools_v1_plain | gpt-oss-120b | 200 | 85.5% | 90.5% | 5 | 0.56 | 1.12 | 0.139 | 1 |
| nemotron-lightning-3p5-30b-a3b_tools_v3_misses_mt4096 | nemotron-lightning-3p5-30b-a3b | 200 | 81.5% | 86.2% | 17 | 3.37 | 11.26 | 0.334 | 1 |
| nemotron-lightning-3p5-30b-a3b_json_v1_plain | nemotron-lightning-3p5-30b-a3b | 200 | 78.5% | 81.0% | 33 | 1.75 | 3.60 | 0.136 | 1 |
| nemotron-lightning-3p5-30b-a3b_tools_v1_plain | nemotron-lightning-3p5-30b-a3b | 200 | 73.9% ± 1.8% | 77.1% | 39 | 1.94 | 4.42 | 0.159 | 4 |
| nemotron-lightning-3p5-30b-a3b_tools_v2_rubric | nemotron-lightning-3p5-30b-a3b | 200 | 67.9% ± 2.7% | 70.6% | 54 | 2.49 | 4.71 | 0.186 | 4 |
| nemotron-lightning-3p5-30b-a3b_json_v2_rubric | nemotron-lightning-3p5-30b-a3b | 200 | 67.5% | 69.2% | 58 | 2.51 | 4.56 | 0.184 | 1 |
| nemotron-lightning-3p5-30b-a3b_json_v2_rubric_json_schema | nemotron-lightning-3p5-30b-a3b | 200 | 66.5% | 68.2% | 60 | 2.55 | 4.60 | 0.186 | 1 |
| nemotron-lightning-3p5-30b-a3b_tools_v2_rubric_required | nemotron-lightning-3p5-30b-a3b | 200 | 66.5% | 69.8% | 53 | 2.42 | 4.89 | 0.190 | 1 |
| sft_muse-glimmer-30b_base_json_v1_plain | muse-glimmer-30b#lora-sft-base | 200 | 65.5% | 67.5% | 57 | 0.00 | 3.32 | 2.165 | 1 |
| nemotron-lightning-3p5-30b-a3b_json_v2_rubric_shots5 | nemotron-lightning-3p5-30b-a3b | 200 | 63.5% | 65.0% | 67 | 2.85 | 4.99 | 0.285 | 1 |

**Reading the table.**
- Phase 4 baselines at max_tokens 1024: nemotron 73.9% tools / 78.5% json, glm-5p3-flash 91.5% / 89.5%, gpt-oss-120b 85.5% / 90.5%, deepseek-v4p1-flash 88.0% / 90.0%, glm-5p3 (reasoning low) 90.0% / 92.0% (json on 100 rows), kimi-k3 88.0% (tools, 100 rows).
- Native `tools` vs plain-prompt JSON: no consistent winner (flash +2 for tools, gpt-oss +5 for json, nemotron +4.5 for json at 1024, +0.5 at 4096). The JSON variant needs the parsing guardrail in `score.py` (code fences, `</think>` residue, `parameters` instead of `arguments`).
- Phase 5 on nemotron: rubric prompt 67.9% (1024) / 88.0% (4096) vs plain 73.9% / 88.0%: no gain. 5-shot 63.5%: worse (longer prompt, more reasoning, more truncation). json_schema 66.5%: no gain. `tool_choice: required` with reasoning on: 66.5% (1024). The levers that matter are reasoning off (87.0%, 0.38 s, $0.055/1k) and reasoning off + required (91.0% ± 0.5%, 0 invalid, 0.40 s, $0.054/1k). v3 prompt (rules written from the real misses) 81.5% with reasoning on: worse again; each extra rule makes the model reason longer.
- Routing: nemotron (reasoning off) → glm-5p3-flash reaches 90.0% at 12% escalation ($0.074/1k) and 91.5% at 31% ($0.102/1k). From the best config (required + reasoning off) routing adds nothing: the big models are not more accurate on the rows it gets wrong. Routing from anything to glm-5p3 only adds cost.

## Best small-model result vs. frontier
Best small configuration: nemotron-lightning-3p5-30b-a3b, native tools, plain prompt, `reasoning_effort: none`, `tool_choice: required`: 91.0% ± 0.5% strict over 4 runs (95.2% partial, 0 invalid), p50 0.40 s, $0.054 per 1k requests. Frontier: kimi-k3 88.0% strict (93.5% partial) on 100 rows at $3.16/1k and p50 1.85 s; glm-5p3 90.0% at $1.06/1k and 0.67 s. The small model is 3 points above kimi-k3 at 1/58th the cost and 1 point above glm-5p3 at 1/20th; the cheapest model that matches it is glm-5p3-flash (91.5%, $0.151/1k, 0.93 s), 2.8x the cost and 2.3x the latency for a difference inside seed noise.

## Headroom verdict
The frontier model does not struggle here, but neither does the small model once two harness settings are right: the apparent 14-point gap at the naive baseline (73.9% vs 88.0%) was max_tokens truncation of hidden reasoning, not capability. Gap between best small config and frontier: +3.0 points for the small model (91.0% vs 88.0%), and every model from 30B-A3B to kimi-k3 lands between 88% and 92%, with 9 of 200 rows missed by all of them (BFCL conventions: an unstated year is 2023, cents vs dollars, a "details:" filter prefix, "track": "any"), so the ceiling is about 95%. I would not pick this task for the real hackathon as a "small model closes the gap" story, because there is no gap to close and the judges can check BFCL's public leaderboard. I would pick it as a "cost and latency" story: the measured 58x cost and 4.6x latency reduction at equal or better accuracy is real, reproducible, and the two settings that produce it (reasoning off, forced tool choice) are the kind of thing a team ships the same afternoon. The honest risks: nemotron-lightning is deprecated on 2026-11-07, and a customer catalog with 50+ tools or multi-step calls would need a new test set.

## Misses analysis
18 misses of the best config (`results/nemotron-lightning-3p5-30b-a3b_tools_v1_plain_required_renone.json`, field `reason`). By source: simple_python 97.5%, multiple 96%, live_simple 95%, live_multiple 81.4%, so 13 of 18 are in live_multiple (3 to 8 tools, terse real-user phrasing).
1. **Invented optional arguments (6 rows).** "play baby shark song" → adds `autoplay: true, volume: 50`; a train search adds `number_of_adults: 1` and `_class`; a web search adds `num_results: 5`. Hypothesis: with reasoning off the model fills every parameter that has a default. Fix candidates: a one-line instruction "omit parameters the user did not mention" measured on the no-reasoning config (the rubric prompt that contains it was only measured with reasoning on), or SFT, which teaches exactly this omission pattern.
2. **Unstated year (3 rows).** "March 10th" → 2025-03-10, gold 2023-03-10. BFCL's convention from its creation date; missed by every model. Dataset artifact, not a model error.
3. **Value copied with extra words (3 rows).** "violent crime" vs "violent", "3x^2" vs "3x**2", a paraphrased `statement` instead of the user's exact sentence. Hypothesis: the model normalizes to natural phrasing; the gold wants the enum/verbatim form. A rubric rule fixed none of these when reasoning was on; untested with reasoning off.
4. **Missing required-by-context argument (3 rows).** "Good past history" → `is_excellent: true` not set; `province_id` omitted when the district is in Bangkok; `include_private: true` not inferred from "including his personal details". Hypothesis: these need one inference step that reasoning-off skips; routing on confidence did not catch them (confidence −0.01 to −0.02, same as correct rows).
5. **Wrong function among near-duplicates (1 row).** `generate_image` vs `generate_human_image` for "a man wearing a red dress". Hypothesis: name-level disambiguation needs the description, which the model skims without reasoning.
6. **Type shape (1 row).** `metrics: "view"` instead of `["view"]`, `"None"` strings instead of omitting. Schema says array; JSON-schema-constrained output would fix this one.
7. **URL template left unfilled (1 row).** `?fabricName={fabricName}` plus a separate `fabricName` argument. Ambiguous schema; gold wants it substituted.

## SFT
Muse Glimmer 30B LoRA (rank 8, alpha 16, 1 epoch = 25 steps of batch 16, 394 rows, 242,394 training tokens, lr 1e-4, loss on assistant tokens only) on the Serverless Training API; scored with the training API sampler (no deployment) in the plain-prompt JSON format on the full locked test set, temperature 0.
- Base model before tuning: 65.5% strict, 67.5% partial, 57 invalid (the base model often answers in prose or wraps the call in text), $0.43 for the pass.
- Tuned: **89.5% strict, 94.2% partial, 1 invalid**, $0.26 for the pass (shorter outputs). +24.0 points from 394 examples, which puts a general-purpose 30B model that was not built for tool calling level with the frontier models (88 to 92%) and 1.5 points under the best harness-only nemotron result (91.0%).
- Where the gain came from (row-level diff of base vs tuned): all 57 invalid outputs became valid calls, 45 of them fully correct; 8 of the 12 rows that were valid but wrong were fixed; 5 rows regressed. 6 of the tuned model's 21 misses are in the 9-row "every model misses" set. Sampler latency is not measured (p50 shows 0.00 in the table).
- Training was free (promotion); the two sampler passes cost $0.69 and are in the ledger. Sampler $/1k ($1.32/1k tuned) is a training-API rate, not a serving price, so the SFT row is an accuracy point only on the chart; served as a serverless LoRA it would price like its base model.
- Ran at 00:02 to 00:43 (2 min per optimizer step; the sampler eval ~2 min per 200 rows). No deployment was created (`session closed; no deployment created` in `train_sft.log`).

## Gotchas hit tonight
- **max_tokens 1024 silently truncated nemotron's hidden reasoning on 21% of rows** (`reasoning_tokens` = 1024, empty tool_calls), which the scorer counted as "invalid output". It made the baseline 14 points too low and made every longer prompt look worse. Fix: max_tokens 4096 or `reasoning_effort: none`. PROTOCOL's "512+" is not enough for this model.
- **`reasoning_effort: low` is ignored by nemotron** (same reasoning token count); `none` works. glm-5p3 rejects `none` and accepts `low`.
- **Reasoning tokens bill as output**, so nemotron at default settings ($0.16 to $0.20/1k) costs more than glm-5p3-flash ($0.15/1k). "Small" is not "cheap" until reasoning is off.
- **Price table keyed on the full model id**: passing the short name to `run_eval.py` logged $0. Fixed (normalizes, aborts on unpriced model); affected rows backfilled from token counts (`fix_cost.py`, ledger notes).
- **zsh does not word-split unquoted variables**: a run chain built as `R="--model ..."; python3 run_eval.py $R` failed instantly with nothing in the log. Use bash arrays (`run_renone.sh`).
- BFCL data moved: `data/BFCL_v3_*.json` 404s; now `bfcl_eval/data/BFCL_v4_*.json` (+ `possible_answer/`). Listed via the GitHub API.
- BFCL ground truth is a list of acceptable values per argument with `""` = optional; "exact match" needs the set semantics in `score.py`. 3 live_simple rows have empty acceptable lists; dropped.
- BFCL parameter types are python-ish (`dict`, `float`, `tuple`, `any`); converted to JSON Schema before sending as `tools`.
- Tool names with dots (`math.factorial`) violate the tool-API name pattern; sanitized to `_` and mapped back for scoring.
- `check_leak.py` keys on the last user message; BFCL reuses the same query with different tool sets, so 6 train rows collided with test. Removed from train.
- `firectl` is not installed and the cookbook's own code cannot be run under this session's permission policy; `train_sft.py` uses only the PyPI SDK and the HF tokenizer chat template, verified to render Muse Glimmer's format.
- Muse Glimmer sampler evaluation of 200 rows cost $0.43 per pass, not the $0.31 estimated from token counts; budget it.
- Fireworks account suspended (HTTP 412) 22:04 to ~22:28 with ten agents running; the watcher script resumed the sweep automatically.
- Nemotron-lightning-3p5-30b-a3b reports `deprecationDate` 2026-11-07 on the model endpoint.
