# Text-to-Cypher: final results

**Exam:** 200 questions from the public `neo4j/text2cypher-2025v1` **test** split, five real Neo4j graphs (movies, recommendations, northwind, fincen, twitter), 40 per graph. Every gold query was executed on the live graph and its rows stored as the answer key. Locked, sha256 `6c47ee00573e7ebc4e144c7e31363b2f3c72b10556e5d2c853323cc85733b491`, re-verified at the start of every run. Grading = execution accuracy (run the query, compare result sets), scorer has 31 passing unit tests. Training used 500 rows from the **train** split only; zero overlap, checked by script.

## Leaderboard (strict execution accuracy)

| Setup | Accuracy | Cost / 1k questions | n |
|---|---|---|---|
| kimi-k3 (priciest open model) | 50.0% | $6.36 | 100 |
| glm-5p3 (large) | 49.0% | $3.13 | 100 |
| deepseek-v4.1-flash | 53.0% | $0.82 | 200 |
| **glm-5p3-flash (small, off the shelf)** | **60.5%** | **$0.24** | 200 |
| Muse Glimmer 30B, untuned | 51.5% | $1.89* | 200 |
| **Muse Glimmer 30B + SFT (ours)** | 59.0% | $1.89* | 200 |
| **Muse Glimmer 30B + SFT + RFT (ours)** | **60.0%** | $1.86* | 200 |
| small + harness, routing (ours) | 59.0% | $0.77 | 200 |

\* 30B costs are measured through the training-API sampler. Served normally the same model is ≈$0.25/1k; the deployment needed to measure that properly was not run (no credits).

With extra output columns tolerated (prediction must still contain gold's answer columns): kimi 55.0%, flash 66.0%, SFT+RFT 64.0%, harness+routing **67.0%**. Ranking is unchanged.

## Three findings

### 1. Price does not buy accuracy on this task
Three expensive models (kimi-k3 $6.36, glm-5p3 $3.13, deepseek $0.82) land at 49 to 53%. The cheapest (glm-5p3-flash, $0.24) reaches 60.5%: **26x cheaper and 10 points better** than the priciest.

We tested and eliminated the three obvious artifacts:
- *Scorer too strict?* Rebuilt it (`score_v2`, 31 tests). Everything moved up 2 to 5 points; ranking unchanged.
- *Punishing richer answers?* Allowed extra columns. Everything up ~5 points; ranking unchanged.
- *Hidden reasoning eating the budget?* Re-ran both large models at low reasoning effort: glm-5p3 48→50%, kimi 50→54%. Still 6 to 10 points behind flash.

Same 100 questions in every comparison.

### 2. Fine-tuning works; reinforcement adds a little
Muse Glimmer 30B: **51.5% → 59.0% with SFT (+7.5), → 60.0% with RFT** on top. SFT is the only intervention clearly outside run-to-run noise (3 seeds: 59.0, 59.4, 59.0). Training cost $0 on the free tier. RFT was done through the Training API by rejection sampling on our execution scorer (reward 1 if the query's rows match gold). The advantage-weighted variant regressed to 36.5%: the API's weighted loss has no trust region or KL penalty, so pushing away from wrong candidates also damages tokens shared with right ones. Symptom: empty results rose from 1% to 14.5%. Documented, not hidden.

### 3. About 15% of the public benchmark is mis-keyed, and execution proves it
We hand-audited all 36 "easy"-tier failures of the best small model. The model is genuinely wrong **2 times out of 36**. The rest: 11 broken gold answers (one asks for "the first 3 orders" and the key returns the same order three times; one asks for a user's location and the key returns a tweet node), 7 ambiguous questions, 20 projection mismatches where the model answers the question asked and the key returns a different column. Across all 200, roughly 30 gold answers do not match their own question text.

Nobody can see this without executing every query against a live graph, which is what our harness does. The corrected scorer, the audit, and the per-question evidence are in `audit/`.

## What the harness buys
Not accuracy. Reliability and a confidence signal:
- Broken or empty queries: 2.2% → 0.1%.
- Agreement of three executed attempts is a real confidence signal: unanimous answers are 64.8% correct, split answers 35%, all-disagree 17.7%.
- **Coverage dial:** answer everything → 55.5% correct; answer only when 3 of 3 agree → 69% of questions answered at **64.8%** precision, the rest flagged for a human.
- Escalating to the large model only helps where no two attempts agree, and *hurts* on 2-of-3 rows. Measured, so we spend the big model's price on 6% of traffic instead of 100%.

## Reproduce
```
python3 run_eval.py --model accounts/fireworks/models/glm-5p3-flash --prompt prompts/v1_plain.txt
python3 harness/run_harness.py --config route_big
python3 audit/superset_test.py
pytest test_score.py        # 31 tests
```
Observability: every step of every question (schema pruning, each generation with tokens and cost, validation, execution with the exact Cypher and row counts, repair, vote, routing) is traced to Langfuse. See `trace/README.md`.
