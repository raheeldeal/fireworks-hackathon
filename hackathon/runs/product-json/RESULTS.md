# product-json: messy product listing → strict JSON (8 fields)
Status: partial (phases 1-6 and 8-11 complete; phase 7 free Muse Glimmer SFT not run: the account's single serverless-training slot was held by sibling runs for the whole 2 h retry window, see phase-7 note)
Test set: 200 rows, sha256 55fec063858774d3940fb22a7fe3d3102bc39ea35992c812e6a1d679815dfa23, source synthetic (gold attributes sampled; brand strings from https://huggingface.co/datasets/tasksource/esci; prose written by gpt-oss-120b and regex-verified against the gold; see DECISIONS.md)
Leak check:
```
test set: 200 rows, sha256 55fec063858774d3
data/train.jsonl: 223 rows, 0 overlap with test
ft/train_messages.jsonl: 223 rows, 0 overlap with test
```
Spend: $2.61 inference, $0.00 training (from ledger.csv; includes $0.13 data generation and $0.07 pilots; sampler tokens for phase 7 are appended to the ledger when it runs)

Headline metric = **all 8 fields correct** after schema validation and normalisation. Field mean = average per-field accuracy. Invalid = did not parse or violated the schema (scores 0 on all fields). $/1k = Fireworks serverless list price × measured tokens (reasoning tokens included).

## Results table
| config | model | accuracy (all 8 fields) | invalid | p50 s | p95 s | $/1k | seeds |
|---|---|---|---|---|---|---|---|
| **Baseline: plain prompt** | | | | | | | |
| plain | nemotron-lightning-3p5-30b-a3b (n=200) | 68.0% (fields 94.5%) | 3 | 4.18 | 7.73 | 0.341 | 1 |
| plain | glm-5p3-flash (n=200) | 76.5% (fields 95.7%) | 3 | 1.52 | 3.46 | 0.176 | 1 |
| plain (also wrote the listings) | gpt-oss-120b (n=200) | 69.5% (fields 91.7%) | 10 | 1.22 | 1.64 | 0.243 | 1 |
| plain | deepseek-v4p1-flash (n=200) | 78.5% (fields 96.9%) | 1 | 2.28 | 7.70 | 0.513 | 1 |
| plain | glm-5p3 (n=200) | 70.0% (fields 94.2%) | 4 | 2.21 | 6.40 | 1.833 | 1 |
| plain (frontier) | kimi-k3 (n=100) | 69.0% (fields 95.9%) | 0 | 3.10 | 8.50 | 4.681 | 1 |
| **Interventions** | | | | | | | |
| (a) rubric | glm-5p3-flash (n=200) | 93.0% (fields 98.2%) | 2 | 1.65 | 4.70 | 0.223 | 1 |
| (c) rubric + JSON-schema mode | glm-5p3-flash (n=200) | 93.5% (fields 99.2%) | 0 | 1.66 | 4.44 | 0.223 | 1 |
| (b) rubric + 5-shot | glm-5p3-flash (n=200) | 95.5% (fields 98.6%) | 2 | 1.37 | 3.07 | 0.354 | 1 |
| (a) rubric | nemotron-lightning-3p5-30b-a3b (n=200) | 71.0% (fields 85.3%) | 25 | 6.04 | 12.19 | 0.495 | 1 |
| (c) rubric + JSON-schema mode | nemotron-lightning-3p5-30b-a3b (n=200) | 67.5% (fields 85.3%) | 24 | 5.96 | 11.71 | 0.497 | 1 |
| rubric (frontier, same 100 rows) | kimi-k3 (n=100) | 92.0% (fields 95.5%) | 4 | 2.96 | 6.70 | 5.092 | 1 |
| **(d) Routing** (small answers; escalate when risk ≥ t; invalid always escalates) | | | | | | | |
| rubric → glm-5p3 plain, t=1 (86% escalated) | glm-5p3-flash->glm-5p3 (n=200) | 72.5% (fields 95.1%) | 3 | 3.78 | 11.88 | 1.794 | 1 |
| t=2 (54%) | glm-5p3-flash->glm-5p3 (n=200) | 76.5% (fields 96.1%) | 2 | 3.08 | 11.57 | 1.269 | 1 |
| t=3 (18%) | glm-5p3-flash->glm-5p3 (n=200) | 84.5% (fields 97.5%) | 1 | 1.74 | 7.40 | 0.609 | 1 |
| rubric → kimi rubric, t=1 (82%) | glm-5p3-flash->kimi-k3 (n=100) | 93.0% (fields 96.5%) | 3 | 4.68 | 12.70 | 4.672 | 1 |
| t=2 (55%) | glm-5p3-flash->kimi-k3 (n=100) | 93.0% (fields 96.5%) | 3 | 3.75 | 11.00 | 3.409 | 1 |
| t=3 (22%) | glm-5p3-flash->kimi-k3 (n=100) | 95.0% (fields 97.5%) | 2 | 1.90 | 9.88 | 1.514 | 1 |
| invalid-only (2%) | glm-5p3-flash->kimi-k3 (n=100) | 95.0% (fields 97.5%) | 2 | 1.67 | 5.58 | 0.332 | 1 |
| few-shot → kimi rubric, t=3 (21%) | glm-5p3-flash->kimi-k3 (n=100) | 95.0% (fields 98.5%) | 1 | 1.46 | 6.17 | 1.564 | 1 |
| invalid-only (2%) | glm-5p3-flash->kimi-k3 (n=100) | 95.0% (fields 98.5%) | 1 | 1.35 | 3.07 | 0.436 | 1 |
| **Variance (3 seeds = 3 row orders, temperature 0)** | | | | | | | |
| plain, seeds 7/8/9 | glm-5p3-flash | 76.3% (range 75.0%–77.5%) | 3/2/2 | | | 0.177 | 3 |
| rubric + 5-shot, seeds 7/8/9 | glm-5p3-flash | 95.5% (range 95.0%–96.0%) | 2/1/1 | | | 0.353 | 3 |
| **(7) Fine-tune** | muse-glimmer-30b LoRA (free promo) | see phase-7 note below | | | | | |

Per-field accuracy (seed 7):
| config | model | brand | product_type | color | size | material | price_usd | quantity | is_bundle |
|---|---|---|---|---|---|---|---|---|---|
| plain | glm-5p3-flash | 98% | 98% | 98% | 98% | 97% | 98% | 98% | 80% |
| rubric | glm-5p3-flash | 98% | 99% | 99% | 99% | 98% | 99% | 97% | 96% |
| rubric+json | glm-5p3-flash | 99% | 100% | 100% | 100% | 99% | 100% | 98% | 98% |
| rubric+5-shot | glm-5p3-flash | 98% | 99% | 99% | 99% | 98% | 99% | 98% | 97% |
| plain | kimi-k3 | 99% | 100% | 99% | 100% | 96% | 100% | 98% | 75% |
| rubric | kimi-k3 | 96% | 96% | 96% | 96% | 96% | 95% | 95% | 94% |
| plain | deepseek-v4p1-flash | 99% | 100% | 100% | 98% | 99% | 100% | 99% | 81% |
| plain | glm-5p3 | 96% | 98% | 96% | 97% | 96% | 98% | 94% | 78% |

Chart: `frontier.png` (x = $/1k log, y = all-fields accuracy).

## Best small-model result vs. frontier
glm-5p3-flash with the rubric + 5-shot prompt scores 95.5% all-fields-correct (3 seeds: 95.0–96.0%, 1–2 invalid of 200) at $0.35 per 1k requests and 1.4 s p50; the frontier kimi-k3 scores 69.0% with the plain prompt and 92.0% with the same rubric at $5.09 per 1k and 3.0 s p50. On the identical 100 rows the small model is 94–95% vs. the frontier's 92%: the small model matches or beats the frontier at 14x lower cost, and routing to the frontier adds nothing (95.0% at any threshold).

## Headroom verdict
The frontier does struggle: with a plain prompt every model, kimi-k3 included, lands at 68–79% because the task's hard cases are definitional (multipack vs. bundle, sale vs. list price, "also available in" colours) and the plain prompt does not define them. Almost all of the headroom is captured by prompting, not model size: the rubric alone is +16.5 points on glm-5p3-flash and +23 on kimi-k3, and after the rubric the gap between best small config and frontier is **+3.5 points in favour of the small model** (95.5% vs. 92.0%). What is left (4.5% misses) is about half label ambiguity in the synthetic gold (see misses) and half genuine model error, so a fine-tune can add at most ~2–3 points. **Would I pick it for the real hackathon? Only as the safe fallback.** It gives a clean, credible "small model beats frontier at 14x lower cost" story with bulletproof scoring and a strong business framing, but the win comes from the prompt, which judges may discount, and the frontier ceiling is already high once prompted. A task whose frontier number stays below 85% after a rubric would show training off better.

## Misses analysis
Best config (glm-5p3-flash, rubric + 5-shot, seed 7): 9 misses of 200, is_bundle 4, invalid (brand null) 2, brand 1, quantity 1, material 1.
1. pj-099-3 bed-sheet *set* "includes the fitted sheet plus two matching pillowcases" → predicted is_bundle false, gold true. Hypothesis: the rubric's bundle examples (case, strap, cable) do not cover "set" semantics; a sheet set reads as one product. Partly a gold-definition issue.
2. pj-020-1 same pattern (king sheets "comes WITH two pillowcases and a fitted sheet"). Same hypothesis.
3. pj-010-4 wallet "with keychain & gift box" → bundle false, gold true. Model treats packaging as not an item; defensible, gold is strict.
4. pj-021-4 headphones, gold not bundle → predicted true. Text likely mentions included cable/manual-style accessories; rubric says accessories make a bundle. Definitional edge.
5. pj-065-1 "12 units available" → gold quantity 12, predicted 1. **Gold is wrong here**: the generator rendered the pack count as stock availability. Label-quality miss.
6. pj-025-0 brand "Amazon" → model returned brand null → schema-invalid. The rubric line "Never a marketplace name" fights the gold (ESCI lists Amazon as a brand). Prompt bug; fix: "the brand as written, even if it is a retailer".
7. pj-063-3 brand only in a trailing lowercase sentence after an SEO keyword line → null → invalid. Hypothesis: brand placement at the very end after keyword stuffing is missed; a "scan the whole text" instruction or JSON-schema mode (string required) would force a guess.
8. pj-021-3 brand "msnbcstoremsnbcstore" (a real but garbled ESCI brand string) → predicted "msnbcstore". Model de-duplicates the typo-looking token. Label noise from the real brand list.
9. pj-006-4 "sturdy porcelain construction" → predicted material ceramic, gold null. Porcelain is ceramic; the model is arguably right, the verifier only checked enum words. Label-quality miss.
Net: 4 of 9 misses are label/definition quality, so the realistic ceiling on this test set is ~97–98%, and the frontier's rubric misses (8 of 100) are the same bundle/set cases plus 4 invalid outputs (brand null).

## Phase 7 note (free fine-tune)
Muse Glimmer 30B LoRA SFT is free until 2026-11-30 (docs evidence in DECISIONS.md). `ft/sft_muse.py` (official `fireworks-ai` SDK, own renderer from the public tokenizer's chat template) trains on `data/train.jsonl` (223 rows, leak-checked) and scores the tuned sampler checkpoint on the locked test set via serverless checkpoint sampling, so no deployment is created. Launch returned `429 maximum concurrent serverless training runs for base model muse-glimmer-30b exceeded: in use 1, limit 1` (a sibling run holds the account's only slot). A 5-minute retry loop ran 24 attempts (23:48–01:49 PT) and never got the slot: five sibling runs compete for it and a new holder appears within seconds of each release. **Phase 7 is therefore partial: not run.** A final loop (`ft/sft_retry2.sh`) polls every 60 s until ~05:00 PT and, if it wins the slot, auto-appends a "Phase 7 addendum" with the base and tuned rows to the end of this file. If no addendum is present, reproduce with the command in README.md once the slot is free.

## Gotchas hit tonight
- **Account suspended (HTTP 412)** 22:05–22:32 ("monthly spending limit or unpaid invoice") after $0.02 spend; the shared limit across ten runs. Fixed by the user on the billing page; probe loop resumed the run automatically.
- GLM-5.3 (flash and large) returns HTTP 400 for `reasoning_effort: "none"` ("thinking-only model"). Sibling sessions later found `reasoning_effort: "low"` gives 0 reasoning tokens on GLM; this run did not use it, so GLM costs here include hidden reasoning (~150–200 tokens/row) and are an upper bound.
- All six models return hidden `reasoning_content` billed as completion tokens; nemotron spends ~1,500 tokens thinking per row and hit the 2,000-token cap (empty content), so its runs use max_tokens 4,000.
- glm-5p3 and nemotron as *generators* spent the entire 4,000–6,000 token budget thinking and returned empty content ($0.06 wasted); gpt-oss-120b generated 5 listings per call for $0.0024.
- `response_format: json_schema` on glm-5p3-flash: 0 invalid outputs (vs. 2) and +0.5 points; on nemotron it did nothing (24 vs. 25 invalid: nemotron's failures are reasoning that never terminates, not formatting).
- Rate limits: 429s on ~5% of calls with ten agents; 5 retries over ~1 minute was not enough (14/96 generation batches failed), 9 retries with backoff capped at 90 s was.
- gpt-oss output for a 5-listing batch sometimes exceeded 6,000 tokens → truncated JSON (`Unterminated string`); batches re-run.
- transformers 5: `apply_chat_template(tokenize=True)` returns a BatchEncoding, not a list; use `tokenize=False` then `encode`. `Datum` is a frozen dataclass (cannot attach attributes).
- Serverless training: one concurrent run per base model per account; sibling runs block each other. Listing sessions: `GET /v1/accounts/<acct>/trainingSessions`.
- The auto-mode permission classifier blocked `pip install -e` of the cloned Fireworks cookbook (external code); the PyPI SDK install was allowed, so the SFT loop was re-implemented (~150 lines).
- HF datasets-server returns HTML when pages are fetched in parallel; `tasksource/esci` has brand/colour but no price/size/quantity, hence the synthetic path.
- Verifier lesson: the first draft rejected 33% of generated rows; two checks were too strict (other product types mentioned as context, the word "includes") and one was missing (instruction leaks like "A few minor typos add a charming touch"). Final rules in `gen_data.verify`.

## Phase 7 addendum (auto-appended 02:53 PT)
Muse Glimmer 30B LoRA SFT completed on the serverless training slot. Training $0 (promotion); sampler tokens are in ledger.csv. Total spend now $2.80.

| Run | All-fields | Mean field | Invalid | p50 | $/1k |
|---|---|---|---|---|---|
| muse-glimmer-30b base (serverless sampler, 20 rows) | 95.0% | 99.4% | 0 | 0.00 s | $2.323 |
| muse-glimmer-30b tuned (serverless sampler, 100 rows) | 98.0% | 99.6% | 0 | 0.00 s | $1.458 |
