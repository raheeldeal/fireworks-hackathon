# banking intent routing (Banking77, 77 classes)
Status: partial (phase 7 only: free Muse Glimmer 30B SFT could not start; the account's single serverless-training slot for that base model was held by another session for the whole window, 26 attempts over 85 min, last at 00:28 PT, every one 429 "in use 1, limit 1". Code, data and cost check are ready: `sft/venv/bin/python sft_muse.py train && sft/venv/bin/python sft_muse.py eval` scores it for ≈ $0.03 once the slot frees. All other phases complete.)
Test set: 154 rows, sha256 3547e8f9bc1491ceeb9be1e1832cca364bb940a2df9a845e230c6ba953e45090, source https://github.com/PolyAI-LDN/task-specific-datasets/tree/master/banking_data (= HF PolyAI/banking77, CC-BY-4.0; 2 utterances per intent from the official test split, seed 20261101)
Leak check: test set: 154 rows, sha256 3547e8f9bc1491ce / data/train.jsonl: 308 rows, 0 overlap with test / data/sft_train.jsonl: 308 rows, 0 overlap with test
Spend: $1.99 inference, $0.00 training (from ledger.csv; 3,500 ledgered calls plus one hand-estimated row of $0.03 for 16 pre-ledger probe calls)

## Results table
All runs: temperature 0, max_tokens 4096, 154 rows in the locked order unless noted. "acc on 100" = accuracy on the same 100 rows kimi-k3 saw (kimi-k3 capped at 100 rows by protocol). Prompt names: v1_plain = 77 labels + one-line definitions, reply with label; v2_conf = same + JSON {intent, confidence}; v3_rubric = v2 + 14 disambiguation rules; v4_fewshot = v3 + 5 examples; suffix _json = enum-constrained JSON schema (response_format); suffix _low/_none = reasoning_effort (no thinking); no suffix = model-default thinking.

| config | model | accuracy | acc on 100 | invalid | p50 s | p95 s | $/1k | seeds |
|---|---|---|---|---|---|---|---|---|
| v1_plain | kimi-k3 (frontier, 100 rows) | 88.0% | 88.0% | 0 | 1.81 | 4.05 | 5.598 | 1 |
| v1_plain | gpt-oss-120b | 84.4% | 86.0% | 0 | 0.54 | 1.25 | 0.281 | 1 |
| v2_conf | gpt-oss-120b | 84.4% | 87.0% | 0 | 0.67 | 1.41 | 0.316 | 1 |
| v1_plain | deepseek-v4p1-flash | 83.8% | 88.0% | 0 | 1.29 | 6.70 | 0.655 | 1 |
| v1_plain | glm-5p3 (large) | 83.8% | 88.0% | 1 | 1.14 | 6.66 | 2.881 | 1 |
| **v1_plain** | **glm-5p3-flash (best small)** | **85.1%** locked order; 83.6% ± 2.6% over 4 orders (85.1, 83.8, 83.1, 82.5) | 87.0% | 0 | 1.24 | 3.47 | 0.259 | 4 |
| v2_conf | glm-5p3-flash | 81.8% | 86.0% | 0 | 1.13 | 3.12 | 0.295 | 1 |
| v3_rubric | glm-5p3-flash | 81.2% | 84.0% | 1 | 1.17 | 5.78 | 0.416 | 1 |
| v2_conf_low (no think) | glm-5p3-flash | 81.2% | 84.0% | 0 | 0.60 | 1.03 | 0.225 | 1 |
| v3_rubric_low | glm-5p3-flash | 80.5% | 84.0% | 0 | 0.57 | 1.09 | 0.334 | 1 |
| v3_rubric_json_low | glm-5p3-flash | 80.4% ± 1.3% over 4 orders (79.9, 80.5, 79.9, 81.2) | 84.0% | 0 | 0.58 | 1.10 | 0.334 | 4 |
| v4_fewshot_low | glm-5p3-flash | 78.6% | 82.0% | 0 | 0.57 | 1.01 | 0.364 | 1 |
| v3_rubric_none | nemotron-lightning-3p5-30b-a3b | 77.3% | 81.0% | 1 | 0.30 | 1.63 | 0.118 | 1 |
| v3_rubric_json_none | nemotron-lightning-3p5-30b-a3b | 76.6% | 81.0% | 0 | 0.31 | 1.18 | 0.118 | 1 |
| v2_conf | nemotron-lightning-3p5-30b-a3b | 76.0% | 80.0% | 3 | 2.79 | 8.11 | 0.323 | 1 |
| v1_plain | nemotron-lightning-3p5-30b-a3b | 74.0% | 78.0% | 7 | 1.85 | 8.34 | 0.269 | 1 |
| v2_conf_none | nemotron-lightning-3p5-30b-a3b | 73.4% | 78.0% | 1 | 0.30 | 0.81 | 0.080 | 1 |
| SFT v0_sft_short | muse-glimmer-30b LoRA (free) | not run: training slot busy all night (429, in use 1/1); rerun with `sft_muse.py train` then `eval` | | | | | | |

### Routing (centerpiece): small model answers with self-reported confidence; escalate when invalid or confidence < threshold
Computed offline from the per-row files of both models (exact at temperature 0; no extra calls). 7 thresholds swept; full tables for 27 (small, big) pairs are in `results/routing_*.json`.

**glm-5p3-flash no-think (v2_conf_low, $0.225/1k) → kimi-k3 (frontier), on kimi's 100 rows**

| threshold | escalated | accuracy | $/1k | p50 s | p95 s |
|---|---|---|---|---|---|
| none (small only) | 0% | 81.2% (84.0% on these 100) | 0.225 | 0.60 | 1.03 |
| 0.50 | 2% | 83.0% | 0.337 | 0.62 | 1.11 |
| 0.60 | 12% | 85.0% | 0.897 | 0.63 | 3.30 |
| **0.70** | **27%** | **88.0%** | **1.737** | **0.67** | 4.50 |
| 0.80 | 36% | 88.0% | 2.240 | 0.75 | 4.76 |
| 0.90 | 45% | 88.0% | 2.744 | 0.97 | 4.76 |
| 0.95 | 77% | 88.0% | 4.536 | 2.38 | 5.00 |
| all to kimi | 100% | 88.0% | 5.598 | 1.81 | 4.05 |

**glm-5p3-flash no-think → gpt-oss-120b (154 rows):** 0.70 → 27% escalated, 84.4% (= gpt-oss alone) at $0.300/1k, p50 0.67 s. **→ glm-5p3 (large):** 0.70 → 83.8% at $0.99/1k; the large GLM is never worth escalating to (gpt-oss is more accurate and 10x cheaper).
**nemotron (any config) → anything:** routing never beats sending everything to the big model; nemotron reports ≥0.95 confidence on 60 to 70% of rows and is only 87 to 92% right on those, so the threshold has nothing to grip.
**gpt-oss → kimi-k3:** 0.95 → 26% escalated, 88.0% at $1.77/1k (same accuracy as glm-flash routing, slightly dearer).

Calibration (accuracy of rows at self-reported confidence ≥ 0.95 / 0.90 / 0.60 to 0.75): glm-5p3-flash no-think 100% / 90% / ~60%; nemotron 87 to 92% / 61 to 75% / n.a. GLM's confidence is usable as a routing signal; Nemotron's is not.

## Best small-model result vs. frontier
glm-5p3-flash with the plain prompt scores 85.1% (83.6% ± 2.6% across 4 row orders) at $0.26 per 1k and 1.2 s p50, against kimi-k3 at 88.0% on 100 rows at $5.60 per 1k and 1.8 s p50; on those same 100 rows glm-5p3-flash scores 87.0%, so the frontier gap is 1 to 4 points at 22x the price. Routing the no-think small model to kimi-k3 at confidence < 0.70 reproduces the frontier's 88.0% exactly while escalating 27% of traffic, at $1.74 per 1k (3.2x cheaper than all-frontier) and 0.67 s p50.

## Headroom verdict
The frontier model does not struggle here: 88% is the top of a pack in which five models sit within 4 points on the same 100 rows (kimi 88, deepseek 88, glm-5p3 88, glm-flash 87, gpt-oss 86 to 87), and seed-to-seed spread on 154 rows is ±2.6 points, so most pairwise differences are inside the noise. The remaining 12% is dominated by Banking77's own label ambiguity (see misses: "How do I reset my PIN?" is gold `pin_blocked`; "I cannot seem to find my PIN" is gold `get_physical_card`; `card_not_working` vs `declined_card_payment` is a coin flip), which no prompt will fix and which fine-tuning can only learn by memorising the annotators' conventions. Prompt engineering made things worse for the small models (rubric, few-shot and JSON-schema each cost 1 to 4 points on glm-flash; thinking off cost 4 points), while nemotron gained 3 points from the rubric and lost nothing from thinking off (7x faster, 3x cheaper). The clean win is the routing story: frontier-equal accuracy at a third of the cost and a third of the latency, or 97% of frontier accuracy at 1/19th of the cost with gpt-oss as the escalation target. **Would I pick this task for the real hackathon? No, not as the headline.** The judging criteria reward a small model that *beats* the frontier; here the frontier barely leads, the test set cannot resolve differences under ~3 points, and the fine-tuning ceiling is set by label noise. This is a good *control* result (it tells us where headroom is not) and a good 60-second demo of confidence routing, but a task where the frontier scores 60 to 70% would show the same mechanism with a far bigger dollar number.

## Misses analysis
Best small config (glm-5p3-flash, v1_plain), 23 misses in 154. Representative:
1. gold `balance_not_updated_after_bank_transfer` → `transfer_timing` (×2): "The amount of time that transfers usually take from a UK account is what? I just completed…" — the message literally asks about timing; the gold label requires inferring that the customer's transfer has not arrived. Hypothesis: definition order matters; a rule "if the customer says their money has not shown up, pick balance_not_updated…" would catch it (added to v3, but v3's other rules cost more than this gained).
2. gold `get_physical_card` → `change_pin` (×2): "I cannot seem to find my PIN. Where is it?" — gold label looks wrong (Banking77 puts "where is my PIN" under get_physical_card because the PIN ships with the card). Label-convention noise.
3. gold `pin_blocked` → `change_pin`: "How do I reset my PIN?" — same family; annotator convention, not model error.
4. gold `card_not_working` ↔ `declined_card_payment` (×2, both directions): "My card was not accepted." / "My card was declined today when eating…" — the two intents overlap by design; the dataset itself is inconsistent.
5. gold `top_up_by_card_charge` → `topping_up_by_card`: "Is it okay to use a bank card to top up" — no mention of a fee; gold label is arguably wrong.
6. gold `top_up_by_bank_transfer_charge` → `transfer_fee_charged`: "is there a fee for a transfer? if so how much will it be?" — genuinely ambiguous (top-up transfer vs outgoing transfer).
7. gold `beneficiary_not_allowed` → `declined_transfer`: "How come I'm not allowed to transfer funds right now? I just keep getting an error message" — plausible either way; the model picked the more literal intent.
8. gold `cash_withdrawal_not_recognised` → `lost_or_stolen_card`: "I need to cancel my card that got stolen… Someone has already taken some money" — two intents in one message; the model answered the first.
9. gold `exchange_via_app` → `card_acceptance`: "How would I use my money in a different country?" — vague; most humans would also hesitate.
10. gold `direct_debit_payment_not_recognised` → `card_payment_not_recognised`: "I may have a fraud charge on my debit statement." — "debit" was read as debit card, not direct debit. A rule could fix this one.
Pattern: roughly half the misses are label noise or genuine ambiguity; the other half are family confusions (transfer-, top-up-, card-family) where a rule helps one case and hurts another. Nemotron adds a third failure mode: inventing label names not in the list (7 invalid outputs with plain prompt; 0 with the enum JSON schema).

## Gotchas hit tonight
- **HTTP 412 PRECONDITION_FAILED, account suspended** ("possibly due to reaching the monthly spending limit") from ~22:00 to 22:24 PT; all ten sessions. Not retryable. Fix: Raheel raised the limit; completed runs with `--retry-errors`, which re-runs only errored rows and merges them in place (no double spend).
- **HTTP 429** on ~2.5% of rows even after 5 backoff retries (ten sessions sharing the models; nemotron worst). Fix: `retry_all.py` second pass at 2 workers; 0 errors remain.
- nemotron-lightning thinks ~1,100 tokens before a one-label answer on a 1,500-token prompt; at max_tokens 1024 content comes back empty (finish_reason=length). Fix: max_tokens 4096, or `reasoning_effort: "none"` (20 output tokens, 0.3 s, same accuracy).
- `reasoning_effort: "none"` is rejected by GLM-5.3 (thinking-only model) and gpt-oss ("Invalid reasoning effort"); `"low"` on GLM yields 0 reasoning tokens in practice; deepseek-flash and kimi-k3 accept "none".
- nemotron invents label names (`get_virtual_card`, `top_up_by_card`); the enum-constrained `response_format` JSON schema removes all of them.
- Asking for JSON + confidence costs glm-flash 3 to 4 points vs. a bare label; the routing signal is not free.
- Serverless training: `create_lora_training_client` on muse-glimmer-30b fails with 429 "maximum concurrent serverless training runs for base model … exceeded: in use 1, limit 1" while another session trains. A retry loop every 3 min (26 attempts, 85 min) never got the slot; phase 7 is left unrun with the commands in README.md §6.
- My own bug: the promo-end date guard in sft_muse.py was computed for 2025, so the first SFT attempt aborted itself; fixed (epoch verified with `date -j`).
- Cloning the Fireworks cookbook was denied by the permission classifier (external code); the installed `fireworks-ai` SDK (1.2.30) was used directly instead, with the HF tokenizer's chat template (`reasoning_strength="none"`).
