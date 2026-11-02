# Text-to-Cypher harness: results

Test set: `data/test.jsonl`, 200 rows, sha256 `6c47ee00573e7ebc4e144c7e31363b2f3c72b10556e5d2c853323cc85733b491` (read fresh and checked against `data/TEST_HASH` at the start of every run). Scored by executing on the live Neo4j demo graphs, strict result-set equality (`score.py`). Small model glm-5p3-flash; big model glm-5p3. Every number below comes from `results/harness_<config>.json`; reproduce with `harness/run_harness.py --config <name> [--reasoning default] [--seed N]`, then `harness/report.py`.

Spend: $2.41 of the $6 cap (`harness/ledger.csv`): $1.50 glm-5p3-flash, $0.91 glm-5p3. No deployments.

## Headline

**The harness makes the small model reliable, not more accurate.** Over 3 repeated runs each, plain glm-5p3-flash scores 53.0% (range 52.5 to 54.0) and the best harness, `repair1` at default reasoning, scores 53.3% (53.0 to 54.0). Voting and routing land at 51.7% and 51.9%. All of these are within run-to-run noise of each other (about ±2 points). What the harness does change: queries that fail or return nothing drop from 2.2% to 0.3%, and the vote gives a confidence signal that separates 62%-correct answers from 18%-correct ones.

Why the ceiling: most misses run fine and return the wrong rows. Under the lenient metric (extra columns allowed, properties vs whole nodes) the same answers score about 65%, and many remaining "wrong" rows are ties under `LIMIT` or a defensible second reading of the question. The harness cannot see those mistakes because nothing errors.

## Results table (one run each, 200 rows)

`_rdefault` = model's default reasoning; everything else uses `reasoning_effort: low` (the API rejects `none` for GLM-5.3: "thinking-only model").

| config | n | accuracy | lenient | error/invalid | empty | p50 s | p95 s | $/1k | calls/row | escalation |
|---|---|---|---|---|---|---|---|---|---|---|
| baseline glm-5p3-flash (default reasoning, BASELINES.md run) | 200 | 57.0% | 69.5% | 0.5% | 0.5% | 1.62 | 4.31 | $0.241 | 1 | - |
| plain_rdefault (same as baseline, harness runner) | 200 | 52.5% | 66.0% | 1.0% | 1.5% | 1.63 | 4.66 | $0.235 | 1 | - |
| plain, reasoning low (from validate_only run, no gate) | 200 | 48.0% | - | 1.5% | 2.5% | 1.07 | 1.72 | $0.148 | 1 | - |
| validate_only | 200 | 48.0% | 58.5% | 3.0% | 1.5% | 1.07 | 1.72 | $0.148 | 1.0 | - |
| repair1 | 200 | 50.0% | 62.0% | 0.5% | 1.0% | 1.06 | 2.31 | $0.157 | 1.05 | - |
| vote3 | 200 | 52.0% | 65.5% | 0.0% | 0.0% | 1.24 | 4.90 | $0.474 | 3.18 | - |
| route_big (escalate when no two agree) | 200 | 55.0% | 67.5% | 0.0% | 0.0% | 1.15 | 5.82 | $0.771 | 3.26 | 6.0% |
| prune_repair1 | 200 | 47.5% | 60.0% | 0.5% | 2.5% | 0.94 | 2.12 | $0.131 | 1.06 | - |
| repair1_fewshot | 200 | 52.0% | 63.0% | 0.0% | 0.0% | 0.93 | 2.39 | $0.161 | 1.07 | - |
| route_big_u (escalate unless 3/3 agree) | 200 | 50.5% | 66.0% | 0.5% | 0.0% | 1.22 | 22.27 | $1.895 | 3.53 | 31.5% |
| repair1_rdefault | 200 | 53.0% | 66.5% | 0.0% | 0.0% | 1.70 | 6.22 | $0.252 | 1.03 | - |
| vote3_rdefault | 200 | 52.0% | 64.5% | 0.0% | 0.0% | 1.97 | 8.11 | $0.779 | 3.10 | - |
| route_big_u_rdefault | 200 | 50.5% | 65.0% | 0.5% | 0.0% | 2.33 | 21.11 | $2.324 | 3.44 | 32.5% |

Latency is wall-clock per question including Neo4j execution; the three vote chains run in parallel.

### Repeated runs (the honest comparison)

| config | runs | mean accuracy | range | mean lenient | mean error+empty | mean $/1k |
|---|---|---|---|---|---|---|
| repair1_rdefault | 3 | 53.3% | 53.0 to 54.0% | 66.2% | 0.3% | $0.263 |
| plain_rdefault | 3 | 53.0% | 52.5 to 54.0% | 65.2% | 2.2% | $0.240 |
| route_big | 4 | 51.9% | 50.0 to 55.0% | 65.1% | 0.1% | $0.874 |
| vote3 | 3 | 51.7% | 49.5 to 53.5% | 64.2% | 0.2% | $0.479 |

The single route_big run at 55.0% was the lucky end of a 50.0 to 55.0 range. Quote 51.9%.

### Accuracy by tier (one run each; easy 70 rows, medium 87, hard 43)

| config | easy | medium | hard |
|---|---|---|---|
| plain_rdefault | 47.1% | 56.3% | 53.5% |
| plain (low) | 42.9% | 54.0% | 44.2% |
| repair1 | 42.9% | 57.5% | 46.5% |
| vote3 | 44.3% | 56.3% | 55.8% |
| route_big | 44.3% | 60.9% | 60.5% |
| prune_repair1 | 44.3% | 52.9% | 41.9% |
| repair1_fewshot | 42.9% | 60.9% | 48.8% |
| repair1_rdefault | 45.7% | 58.6% | 53.5% |
| vote3_rdefault | 41.4% | 57.5% | 58.1% |

The one consistent tier pattern: voting helps the **hard** tier (44% to 56-58% at reasoning low) and does nothing for easy. Easy rows are the weakest tier for every config; they are short questions where the gold picks one of several reasonable projections, so the miss is in the scoring, not the reasoning.

## What each element bought, and why

**1. validate.** Zero accuracy change (48.0% gated vs 48.0% ungated). It rejected 3 queries in the reasoning-low run and all 3 were wrong anyway (bad relationship direction, a property on the wrong node), so it costs no correct answers. Run on the 200 gold queries it passes 196; the 4 it flags (t020, t047, t083, t138) are real gold defects that use properties not in the graph (for example `Order.discount`) and return 0 or null, so those rows reward a broken query. Value: a safety gate (no writes, no admin calls, one statement) and a precise error message to feed repair, not a score lift.

**2. generate_and_repair (repair1).** Removes almost all failed and empty queries (2.2% to 0.3% across 3 runs at default reasoning) but adds only +0.3 points on average, because repair fires on 3 to 5% of rows. The model rarely writes broken Cypher; it writes valid Cypher that answers a slightly different question. The single-run +2 points at reasoning low (48.0% to 50.0%) is mostly noise: 9 of 190 untouched rows flipped between runs even at temperature 0.

**2b. repair1_fewshot.** 52.0% vs 50.0% for repair1 at reasoning low, one run each. On the rows it repaired, 8 of 13 ended correct vs 3 of 10 for plain repair, which suggests retrieved examples make the retry better. The sample is too small to claim more than "promising, cheap (+$0.004 per 1k)".

**3. vote3.** 51.7% mean over 3 runs at reasoning low, +3.7 points over the single plain run at the same reasoning level, mostly from the hard tier (44% to 56%). Costs 3.2x calls ($0.48 per 1k). At default reasoning it adds nothing over a single call (52.0% vs 53.0%). Its main value is the agreement signal, below.

**4. route (route_big).** Escalating the 6 to 9% of rows where no two attempts agree: 51.9% mean over 4 runs, about level with vote3. glm-5p3 was right on 26% of those escalated rows vs 20% for the small model's own answer (35 row-runs pooled), so it is a small, real gain on a small slice. Escalating every non-unanimous row (route_big_u, 31.5% escalated) made things worse: on 2/3-agreement rows glm-5p3 scored 25.7% vs 33.3% for the small model, at 2.5x the cost and a 22 s p95. The big model is not better than the small one on this test set (BASELINES.md agrees: glm-5p3 and kimi-k3 sit within a few points of flash).

**5. schema_prune.** Saves 21.1% of first-call prompt tokens (168,297 to 132,784; 158 rows pruned, 42 fell back to the full schema) and lowers cost to $0.131 per 1k, but costs 2.5 points (47.5% vs 50.0%) and raises empty results to 2.5%. Offline, pruning drops a label or relationship the gold query needs on 6 of 200 rows. Schemas here are only 1 to 4 KB, so there is little to save; not worth it at this size.

## Calibration (full detail in `CALIBRATION.md`)

Pooled over 5 vote runs (1,000 row-runs):

| agreement | share | small-model accuracy |
|---|---|---|
| 3/3 | 69.8% | 61.7% |
| 2/3 | 24.0% | 35.0% |
| none | 6.2% | 17.7% |

Agreement is a real confidence signal: unanimous answers are 3.5x as likely to be right as split ones. But glm-5p3 is not much better on the hard rows, so the data supports **flagging low-agreement answers for the analyst** more than paying a bigger model to retry them.

## What a human should decide
1. **Pitch framing.** The honest claim is "same accuracy as the plain small model, near-zero broken queries, and a confidence flag that marks which 30% of answers to double-check", not "the harness beats the baseline". Accuracy gains here are inside noise.
2. **Gold defects.** Drop or relabel t020, t047, t083, t138 (gold uses properties absent from the graph). Consider a lenient or hand-checked score for the 17 `LIMIT`-without-`ORDER BY` rows; that is where much of the "wrong" mass is.
3. **Reasoning setting.** Default reasoning is worth 3 to 5 points over `low` for single calls and costs about 1.6x. Use default for the shipped config.
4. **Fine-tune data.** The 3/3-agreement answers that also match gold are the cleanest training rows if the team still runs SFT.
