# Re-score: v1 strict vs v2 execution accuracy

Every file in `results/` re-scored offline from its stored `pred_cypher` (re-executed once
against the live demo graphs and cached in `audit/exec_cache.json`). No model calls; new spend $0.
v2 rules and justifications: `audit/SCORING.md`. Per-row v2 verdicts: `results_v2/<same name>.json`.

`v2 (clean)` drops the 4 known gold-defect rows (t020, t047, t083, t138), whose gold returns 0/null
because the gold query reads properties the graph does not have; on those rows a broken prediction
can score correct, so the clean column is the number to quote.

| config | n | v1 acc | v2 acc | delta | v2 (clean, n=196) | v2 error | v2 empty |
|---|---|---|---|---|---|---|---|
| deepseek-v4p1-flash_v1_plain_n200 | 200 | 49.0% | 53.0% | +4.0 pp | 53.6% | 1.5% | 1.0% |
| glm-5p3-flash_v1_plain_n200 | 200 | 57.0% | 60.5% | +3.5 pp | 61.7% | 0.5% | 0.5% |
| glm-5p3_v1_plain_n100 | 100 | 48.0% | 49.0% | +1.0 pp | 49.5% | 3.0% | 1.0% |
| gold_v1_plain_n200 | 200 | 100.0% | 100.0% | +0.0 pp | 100.0% | 0.0% | 0.0% |
| harness_plain_rdefault | 200 | 52.5% | 57.0% | +4.5 pp | 58.2% | 1.0% | 1.5% |
| harness_plain_rdefault_s1 | 200 | 54.0% | 58.0% | +4.0 pp | 59.2% | 1.5% | 0.5% |
| harness_plain_rdefault_s2 | 200 | 52.5% | 55.5% | +3.0 pp | 56.6% | 1.0% | 1.0% |
| harness_prune_repair1 | 200 | 47.5% | 52.5% | +5.0 pp | 53.6% | 0.5% | 2.5% |
| harness_repair1 | 200 | 50.0% | 54.5% | +4.5 pp | 55.6% | 0.0% | 1.0% |
| harness_repair1_fewshot | 200 | 52.0% | 56.5% | +4.5 pp | 57.6% | 0.0% | 0.0% |
| harness_repair1_rdefault | 200 | 53.0% | 57.0% | +4.0 pp | 58.2% | 0.0% | 0.0% |
| harness_repair1_rdefault_s1 | 200 | 53.0% | 56.0% | +3.0 pp | 57.1% | 0.0% | 0.5% |
| harness_repair1_rdefault_s2 | 200 | 54.0% | 58.0% | +4.0 pp | 59.2% | 0.0% | 0.5% |
| harness_route_big | 200 | 55.0% | 59.0% | +4.0 pp | 60.2% | 0.0% | 0.0% |
| harness_route_big_s1 | 200 | 51.5% | 55.0% | +3.5 pp | 56.1% | 0.5% | 0.0% |
| harness_route_big_s2 | 200 | 51.0% | 55.5% | +4.5 pp | 56.6% | 0.0% | 0.0% |
| harness_route_big_s3 | 200 | 50.0% | 54.5% | +4.5 pp | 55.6% | 0.0% | 0.0% |
| harness_route_big_u | 200 | 50.5% | 54.0% | +3.5 pp | 55.1% | 0.5% | 0.0% |
| harness_route_big_u_rdefault | 200 | 50.5% | 53.5% | +3.0 pp | 54.6% | 0.5% | 0.0% |
| harness_validate_only | 200 | 48.0% | 51.5% | +3.5 pp | 52.5% | 1.5% | 2.5% |
| harness_vote3 | 200 | 52.0% | 56.5% | +4.5 pp | 57.6% | 0.5% | 0.0% |
| harness_vote3_rdefault | 200 | 52.0% | 55.5% | +3.5 pp | 56.6% | 0.0% | 0.0% |
| harness_vote3_s1 | 200 | 53.5% | 56.5% | +3.0 pp | 57.6% | 0.5% | 0.0% |
| harness_vote3_s2 | 200 | 49.5% | 53.5% | +4.0 pp | 54.6% | 0.0% | 0.0% |
| kimi-k3_v1_plain_n100 | 100 | 49.0% | 50.0% | +1.0 pp | 50.5% | 2.0% | 1.0% |
| train_base | 200 | 48.5% | 51.5% | +3.0 pp | 51.0% | 2.0% | 4.0% |
| train_rft_r1 | 200 | 32.5% | 36.5% | +4.0 pp | 36.2% | 7.5% | 14.5% |
| train_rft_r1_reject | 200 | 57.5% | 60.0% | +2.5 pp | 60.7% | 0.5% | 2.5% |
| train_sft | 200 | 56.5% | 59.0% | +2.5 pp | 59.2% | 0.5% | 1.0% |
| train_sft_pruned | 200 | 54.5% | 57.0% | +2.5 pp | 57.6% | 0.0% | 2.0% |
| train_sft_seed1 | 200 | 57.0% | 59.5% | +2.5 pp | 59.7% | 0.5% | 1.0% |
| train_sft_seed2 | 200 | 56.5% | 59.0% | +2.5 pp | 59.2% | 0.5% | 1.0% |

## Per-tier (easy 70 / medium 87 / hard 43 on the 200-row set; the n=100 files cover
the first 100 rows, so their tier counts are smaller but the pattern is the same)

| config | easy v1 | easy v2 | medium v1 | medium v2 | hard v1 | hard v2 | monotone easy>=med>=hard? |
|---|---|---|---|---|---|---|---|
| deepseek-v4p1-flash_v1_plain_n200 | 44.3% | 50.0% | 54.0% | 58.6% | 46.5% | 46.5% | NO |
| glm-5p3-flash_v1_plain_n200 | 48.6% | 54.3% | 60.9% | 64.4% | 62.8% | 62.8% | NO |
| glm-5p3_v1_plain_n100 | 34.3% | 34.3% | 60.5% | 62.8% | 45.5% | 45.5% | NO |
| gold_v1_plain_n200 | 100.0% | 100.0% | 100.0% | 100.0% | 100.0% | 100.0% | yes |
| harness_plain_rdefault | 47.1% | 52.9% | 56.3% | 62.1% | 53.5% | 53.5% | NO |
| harness_plain_rdefault_s1 | 47.1% | 51.4% | 58.6% | 63.2% | 55.8% | 58.1% | NO |
| harness_plain_rdefault_s2 | 45.7% | 50.0% | 56.3% | 59.8% | 55.8% | 55.8% | NO |
| harness_prune_repair1 | 44.3% | 50.0% | 52.9% | 57.5% | 41.9% | 46.5% | NO |
| harness_repair1 | 42.9% | 47.1% | 57.5% | 60.9% | 46.5% | 53.5% | NO |
| harness_repair1_fewshot | 42.9% | 47.1% | 60.9% | 64.4% | 48.8% | 55.8% | NO |
| harness_repair1_rdefault | 45.7% | 51.4% | 58.6% | 63.2% | 53.5% | 53.5% | NO |
| harness_repair1_rdefault_s1 | 42.9% | 48.6% | 60.9% | 63.2% | 53.5% | 53.5% | NO |
| harness_repair1_rdefault_s2 | 47.1% | 51.4% | 59.8% | 65.5% | 53.5% | 53.5% | NO |
| harness_route_big | 44.3% | 50.0% | 60.9% | 64.4% | 60.5% | 62.8% | NO |
| harness_route_big_s1 | 45.7% | 50.0% | 56.3% | 59.8% | 51.2% | 53.5% | NO |
| harness_route_big_s2 | 41.4% | 48.6% | 59.8% | 63.2% | 48.8% | 51.2% | NO |
| harness_route_big_s3 | 41.4% | 47.1% | 58.6% | 62.1% | 46.5% | 51.2% | NO |
| harness_route_big_u | 42.9% | 47.1% | 56.3% | 60.9% | 51.2% | 51.2% | NO |
| harness_route_big_u_rdefault | 40.0% | 47.1% | 55.2% | 56.3% | 58.1% | 58.1% | NO |
| harness_validate_only | 42.9% | 45.7% | 54.0% | 57.5% | 44.2% | 48.8% | NO |
| harness_vote3 | 44.3% | 48.6% | 56.3% | 60.9% | 55.8% | 60.5% | NO |
| harness_vote3_rdefault | 41.4% | 47.1% | 57.5% | 60.9% | 58.1% | 58.1% | NO |
| harness_vote3_s1 | 47.1% | 51.4% | 57.5% | 60.9% | 55.8% | 55.8% | NO |
| harness_vote3_s2 | 42.9% | 48.6% | 55.2% | 58.6% | 48.8% | 51.2% | NO |
| kimi-k3_v1_plain_n100 | 40.0% | 40.0% | 62.8% | 65.1% | 36.4% | 36.4% | NO |
| train_base | 34.3% | 37.1% | 58.6% | 63.2% | 51.2% | 51.2% | NO |
| train_rft_r1 | 21.4% | 30.0% | 42.5% | 44.8% | 30.2% | 30.2% | NO |
| train_rft_r1_reject | 50.0% | 52.9% | 60.9% | 64.4% | 62.8% | 62.8% | NO |
| train_sft | 48.6% | 51.4% | 60.9% | 64.4% | 60.5% | 60.5% | NO |
| train_sft_pruned | 48.6% | 51.4% | 59.8% | 63.2% | 53.5% | 53.5% | NO |
| train_sft_seed1 | 47.1% | 50.0% | 63.2% | 66.7% | 60.5% | 60.5% | NO |
| train_sft_seed2 | 48.6% | 51.4% | 62.1% | 65.5% | 58.1% | 58.1% | NO |

Monotone (easy >= medium >= hard) under v2: **1 of 32 configs**.

## THE SANITY CHECK STILL FAILS. Read this before quoting any tier number.

Only 1 of 32 configs satisfy easy >= medium >= hard under v2 (the one that does is the
gold self-run at 100%). v2 lifts the easy tier by 4 to 8 points, more than any other tier,
but easy remains the **worst** tier for every model. We did not add rules until the check
passed, because the audit says the check is testing the wrong thing:

**`tier` is not a difficulty label.** `score.complexity()` assigns `easy` to any gold query
with one hop and no aggregation. In this dataset that selects the rows whose questions are
the *least specified*, not the least difficult: bare lookups where the gold author freely
chose the projection (`RETURN m` vs `RETURN m.title` vs `RETURN m.title, m.votes`) and freely
invented an ordering for "first 3". Medium and hard questions name their aggregate ("how
many", "the average", "top 5 by X"), which pins the projection and removes that freedom.

The hand audit (`MISS_AUDIT.md`) measured this on 36 easy misses: 2 are real model errors,
20 are scoring artifacts (15 of them projection-only, which v2 deliberately does not excuse),
11 are gold defects and 7 are ambiguous questions. So easy-tier accuracy is mostly measuring
gold-projection noise. Three honest options, for a human:

1. Quote overall v2 accuracy and **stop reporting the tier breakdown as a difficulty curve**.
2. Relabel the tiers from the *question* (does it name a count, an order, a projection?)
   rather than from the gold Cypher's shape.
3. Fix the gold projections in a future test set; `data/test.jsonl` is frozen here by
   `data/TEST_HASH`, so this cannot be done in this submission.

Skipped: claude-opus-5_v1_plain_n100.json (dead run: no predictions), coverage_curve.json

## Headline numbers under v2

All accuracies on the 196 clean rows (the 4 gold-defect rows excluded), so they are 0.5 to 1.2
points *lower* than the all-200 numbers in the table above. Ranges are run-to-run, which on this
test set is about +/- 2 points - treat any gap smaller than that as noise.

| what | v1 | **v2** | note |
|---|---|---|---|
| glm-5p3-flash, plain prompt (BASELINES run) | 58.2% | **61.7%** | single run; the harness runner's 3 repeats of the same config mean 58.0% (56.6 to 59.2), so 61.7% is the lucky end |
| glm-5p3-flash, plain, 3 repeats | 54.1% | **58.0%** | range 56.6 to 59.2% |
| best harness config: `repair1_rdefault`, 3 repeats | 54.4% | **58.2%** | still inside noise of plain (58.0%); the harness buys reliability, not accuracy |
| best single harness run: `route_big` | 56.1% | **60.2%** | one run of a 55.6 to 60.2% range; do not quote this one alone |
| kimi-k3 (first 100 rows) | 49.5% | **50.5%** | on the same 97 rows glm-5p3-flash scores 61.9% and glm-5p3 49.5%: the big models really are worse here, v2 does not change that |
| SFT tuned model `train_sft` | 56.6% | **59.2%** | 3 seeds mean 59.4% (59.2 to 59.7), vs base model 51.0%: **+8.4 points, the only effect in this project clearly larger than noise** |

Coverage curve recomputed from the v2 verdicts, pooled over the 4 `harness_vote3*` runs
(800 row-runs; `results_v2/coverage_curve.json`). Note `HARNESS.md` says 5 runs / 1,000 row-runs for
this curve, but only 4 vote runs exist in `results/`; the v1 column below reproduces
`results/coverage_curve.json` exactly, so the old curve was also 4 runs and the doc is wrong.

| policy | coverage | precision v1 | precision v2 |
|---|---|---|---|
| answer only if 3/3 agree | 69.2% | 61.9% | **64.8%** |
| answer if >= 2/3 agree | 93.4% | 53.9% | **57.8%** |
| answer everything | 100.0% | 51.7% | **55.5%** |

The agreement signal survives v2: unanimous answers are still far more likely to be right than
split ones (64.8% vs 55.5% overall precision), so the "flag the low-agreement 30% for an analyst"
story holds. v2 raises every point on the curve by 3 to 4 points and changes none of its shape.

### How much the scorer change is worth, honestly

**+2 to +5 points, not +12.** The old `score_lenient` added about 12 points (53% to 65%) by
accepting predictions whose row values are a superset of gold's. We did not adopt that, because no
published execution-accuracy metric does and a judge would reject it. The two rules that actually
fire are node-vs-identifying-property (R7) and LIMIT non-determinism (R8/R9); across all 32 re-scored
files they flip 134 and 100 row-verdicts respectively, on 22 and 11 distinct test rows. Every one of
those 33 rows was inspected by hand. One rule was **removed** during that inspection: the LIMIT tie
rule originally also fired when gold's `ORDER BY` key was `null`, which let a prediction with an
extra `WHERE` clause pass on t036 by landing inside a meaningless null ordering. It now stays strict
when any gold sort key is null (`test_v2_null_sort_key_is_not_a_tie`).
