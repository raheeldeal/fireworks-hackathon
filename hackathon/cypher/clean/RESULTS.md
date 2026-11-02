# Verified benchmark: 103 questions, graded by result

## How the verified set was built
1. Start from our 200 locked exam questions (public `neo4j/text2cypher-2025v1` test split, 5 live Neo4j graphs).
2. Run every answer key on its live database and keep its returned rows.
3. Two independent models (Kimi K3, GLM 5.3) each see only the question and those returned rows, and judge: do these rows correctly answer the question? They never see any model's attempt.
4. Keep a question only if both say yes: **103 of 200** (judges agreed on 162 of 200). Covers all 5 graphs (fincen 29, northwind 22, movies 19, recommendations 18, twitter 15) and all tiers (39 easy, 38 medium, 26 hard).
5. Known-bad keys were excluded automatically (t015 "first 3 orders" returning one order three times; t122 "user location" returning a tweet; t000 four-way tie at the top-5 cut).

File: `data/test_clean.jsonl`, sha256 in `data/TEST_CLEAN_HASH`. Every judgement with its one-line reason: `clean/judgements.json`.

## How answers are graded
Run the model's query on the live database. If its rows exactly match the verified key's rows, correct. Otherwise, show both sets of rows to the same two judges: "same answer to the question?" Column names, order and extra or missing descriptive columns don't count; entities and values do. Correct only if both judges say same. 187 of 325 re-graded answers were rescued this way; spot checks confirm they are the same answer with a column more or less. Log: `clean/regrade_log.json`.

## Results
| Setup | Accuracy | Δ vs fine-tune base | Δ vs GLM Flash |
|---|---|---|---|
| GLM 5.3 Flash ($0.24/1k) | **88.3%** | +8.7pp significant | baseline |
| Harness: repair once | 87.4% | +7.8pp significant | −1.0 n.s. |
| Harness: route on disagreement | 86.4% | +6.8 n.s. | −1.9 n.s. |
| DeepSeek V4.1 Flash | 86.4% | +6.8 n.s. | −1.9 n.s. |
| Muse Glimmer 30B + SFT | 83.5% | +3.9 n.s. | −4.9 n.s. |
| Muse Glimmer 30B + SFT + RFT | 82.5% | +2.9 n.s. | −5.8 n.s. |
| Muse Glimmer 30B base | 79.6% | baseline | −8.7 significant |
| GLM 5.3 large (49 q) | 79.6% | +2.0 n.s. | −4.1 n.s. |
| Kimi K3 (49 q) | 73.5% | −4.1 n.s. | **−10.2 significant** |
| Claude Opus 5, closed ($9/1k) (49 q) | 71.4% | −6.1 n.s. | **−12.2 significant** |

Significance: paired bootstrap, 95% CI, same questions. Closed and large models were run on the first 100 exam questions, 49 of which are in the verified set; their comparisons are on those 49.

## What it says
1. The cheapest model, GLM 5.3 Flash, is the best: 88.3%, significantly ahead of Kimi K3 (−10.2pp) and Claude Opus 5 (−12.2pp), at 1/37 of Claude's price.
2. Fine-tuning moved Muse Glimmer 30B from 79.6% to 83.5%: positive but not significant on 103 questions. On the unverified 200 it was +7.5pp and significant.
3. The harness's repair step is the only addition that significantly beats the fine-tune baseline, and it brings broken queries to near zero.
4. Most of the original "60%" was the benchmark, not the models: on verified questions graded by result, the same models score 72 to 88%.
