# Held-out graph test: does the Cypher fine-tune generalize?

Built 14:05 to 14:20 PT, 2026-11-02. Spend $0.63 (`heldout/ledger.csv`, cap $3). No deployments created.

## The exam
- **Graph: gameofthrones** (Neo4j demo server, first of the five candidates; it answered a read query in 1.1 s). None of the training or main-exam graphs (movies, recommendations, northwind, fincen, twitter) share its schema.
- **Rows:** all 148 gameofthrones rows in the 2025v1 official TEST split. Gold executed live: 132 returned 1 to 200 rows (2 empty, 14 over 200 rows, 0 errors). 100 kept, seed 2026, same filter as `scripts/lock_sets.py`.
- **Tiers:** the target was the main exam's mix (25 hard / 40 medium / 35 easy), but the pool only has 5 hard and 28 medium rows, so the set is **67 easy, 28 medium, 5 hard**. The hard-tier numbers below are 5 rows and mean nothing on their own.
- File `heldout/test_gameofthrones.jsonl` (same row shape as `data/test.jsonl`, ids h000 to h099), sha256 `b2539c710a123178b7c3c52e59fe18b868a7d239a1e666560b6b78abc510afe9` (`heldout/HASH`).
- Same prompt as the main exam (`prompts/v1_plain.txt`), temperature 0, scored with `score_v2` (the main exam's scorer, including its LIMIT-tie rule; unlimited gold results cached in `gold_unlimited_gameofthrones.json`). v1 strict scores are stored per row as `correct_v1`.
- Muse models sampled through the Training API sampler exactly as `train/rl.py eval` does (reasoning off via the to=user prefill). The SFT+RFT model is the rejection-sampling round (`cypher-r1rej-1204`), the RFT model that did not regress.

## Results

| model | held-out n | held-out (gameofthrones) | main exam n | main exam | delta (pts) |
|---|---|---|---|---|---|
| glm-5p3-flash (default reasoning) | 100 | 56.0% | 200 | 60.5% | -4.5 |
| Muse Glimmer 30B base | 100 | 57.0% | 200 | 51.5% | +5.5 |
| Muse Glimmer + SFT (cypher-sft-1150) | 100 | 60.0% | 200 | 59.0% | +1.0 |
| Muse Glimmer + SFT + RFT (cypher-r1rej-1204) | 100 | 62.0% | 200 | 60.0% | +2.0 |
| kimi-k3 (frontier) | 50 | 48.0% | 100 | 50.0% | -2.0 |

On kimi's 50-row slice: glm-5p3-flash 58%, base 56%, SFT 58%, SFT+RFT 56%, kimi-k3 48%.

Per tier on the held-out graph:

| model | easy (n=67) | medium (n=28) | hard (n=5) |
|---|---|---|---|
| glm-5p3-flash | 55% | 68% | 0% |
| Muse base | 55% | 64% | 40% |
| Muse + SFT | 58% | 75% | 0% |
| Muse + SFT + RFT | 63% | 71% | 0% |
| kimi-k3 (n=36 / 11 / 3) | 47% | 64% | 0% |

Execution errors (query fails to run): base 6%, SFT 1%, SFT+RFT 1%, glm 0%. Five of the base model's six errors are the same Cypher syntax mistake (bad relationship-type syntax); the fine-tunes stopped making it on this unseen graph too.

## Significance (paired bootstrap, 10,000 resamples, same rows for both models)

| comparison | diff | 95% CI | p | rows only A right / only B right |
|---|---|---|---|---|
| SFT vs base, held-out | +3.0 pts | [-6, +12] | 0.57 | 11 / 8 |
| SFT+RFT vs base, held-out | +5.0 pts | [-3, +13] | 0.27 | 11 / 6 |
| SFT+RFT vs SFT, held-out | +2.0 pts | [-5, +9] | 0.67 | 7 / 5 |
| SFT vs glm-5p3-flash, held-out | +4.0 pts | [-5, +13] | 0.46 | 13 / 9 |
| SFT vs base, main 200 (for reference) | +7.5 pts | [+2, +13] | 0.006 | 23 / 8 |

## Verdict
The fine-tune does not clearly generalize. On the five training graphs SFT beats its base by 7.5 points and that gain is real (p = 0.006). On an unseen schema the gain shrinks to 3 points (5 with RFT), the confidence interval spans zero, and 100 rows cannot tell it apart from noise. What does transfer is the narrow, mechanical part: the tuned models stop writing invalid Cypher (errors drop from 6% to 1%), and they do no harm, staying level with or slightly ahead of base and glm-5p3-flash. The safe claim for judges: "Fine-tuning made a 30B model match a frontier-class model on the graphs it trained on; on a graph it never saw, it holds that level but the extra lift is not proven." One more caveat: the base model scores 5.5 points higher here than on the main exam, so gameofthrones is an easier graph for this model family (shorter schema, 579 vs 841 prompt tokens, and almost no hard rows), which leaves less room for the fine-tune to show a gain.

## Files
- `build.py`: builds the test file, HASH and the unlimited-gold cache.
- `run.py`: runs one model (`--kind api` or `--kind muse`), writes `results/<model>.json` in the standard shape with per-row `correct` (score_v2).
- `analyze.py`: tables and bootstrap above (`results/analysis.txt`).
