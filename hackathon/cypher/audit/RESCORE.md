# Re-score: v1 strict vs v2 execution accuracy

Every file in `results/` re-scored offline from its stored `pred_cypher` (re-executed once
against the live demo graphs and cached in `audit/exec_cache.json`). No model calls; new spend $0.
v2 rules and justifications: `audit/SCORING.md`. Per-row v2 verdicts: `results_v2/<same name>.json`.

`v2 (clean)` drops the 4 known gold-defect rows (t020, t047, t083, t138), whose gold returns 0/null
because the gold query reads properties the graph does not have; on those rows a broken prediction
can score correct, so the clean column is the number to quote.

| config | n | v1 acc | v2 acc | delta | v2 (clean, n=196) | v2 error | v2 empty |
|---|---|---|---|---|---|---|---|
| deepseek-v4p1-flash_v1_plain_n200 | 200 | 49.0% | 53.0% | +0.0 pp | 53.6% | 1.5% | 1.0% |
| glm-5p3-flash_v1_plain_n200 | 200 | 57.0% | 60.0% | +0.0 pp | 61.2% | 0.5% | 0.5% |
| glm-5p3_v1_plain_n100 | 100 | 48.0% | 48.0% | +0.0 pp | 48.4% | 3.0% | 1.0% |
| gold_v1_plain_n200 | 200 | 100.0% | 100.0% | +0.0 pp | 100.0% | 0.0% | 0.0% |
| harness_plain_rdefault | 200 | 52.5% | 56.5% | +0.0 pp | 57.6% | 1.0% | 1.5% |
| harness_plain_rdefault_s1 | 200 | 54.0% | 57.0% | +0.0 pp | 58.2% | 1.5% | 0.5% |
| harness_plain_rdefault_s2 | 200 | 52.5% | 55.0% | +0.0 pp | 56.1% | 1.0% | 1.0% |
| harness_prune_repair1 | 200 | 47.5% | 52.0% | +0.0 pp | 53.1% | 0.5% | 2.5% |
| harness_repair1 | 200 | 50.0% | 54.5% | +0.0 pp | 55.6% | 0.0% | 1.0% |
| harness_repair1_fewshot | 200 | 52.0% | 56.5% | +0.0 pp | 57.6% | 0.0% | 0.0% |
| harness_repair1_rdefault | 200 | 53.0% | 56.5% | +0.0 pp | 57.6% | 0.0% | 0.0% |
| harness_repair1_rdefault_s1 | 200 | 53.0% | 55.5% | +0.0 pp | 56.6% | 0.0% | 0.5% |
| harness_repair1_rdefault_s2 | 200 | 54.0% | 57.0% | +0.0 pp | 58.2% | 0.0% | 0.5% |
| harness_route_big | 200 | 55.0% | 59.0% | +0.0 pp | 60.2% | 0.0% | 0.0% |
| harness_route_big_s1 | 200 | 51.5% | 55.0% | +0.0 pp | 56.1% | 0.5% | 0.0% |
| harness_route_big_s2 | 200 | 51.0% | 55.5% | +0.0 pp | 56.6% | 0.0% | 0.0% |
| harness_route_big_s3 | 200 | 50.0% | 54.5% | +0.0 pp | 55.6% | 0.0% | 0.0% |
| harness_route_big_u | 200 | 50.5% | 54.0% | +0.0 pp | 55.1% | 0.5% | 0.0% |
| harness_route_big_u_rdefault | 200 | 50.5% | 53.5% | +0.0 pp | 54.6% | 0.5% | 0.0% |
| harness_validate_only | 200 | 48.0% | 51.5% | +0.0 pp | 52.5% | 1.5% | 2.5% |
| harness_vote3 | 200 | 52.0% | 56.5% | +0.0 pp | 57.6% | 0.5% | 0.0% |
| harness_vote3_rdefault | 200 | 52.0% | 55.5% | +0.0 pp | 56.6% | 0.0% | 0.0% |
| harness_vote3_s1 | 200 | 53.5% | 56.5% | +0.0 pp | 57.6% | 0.5% | 0.0% |
| harness_vote3_s2 | 200 | 49.5% | 53.5% | +0.0 pp | 54.6% | 0.0% | 0.0% |
| kimi-k3_v1_plain_n100 | 100 | 49.0% | 50.0% | +0.0 pp | 50.5% | 2.0% | 1.0% |
| train_base | 200 | 48.5% | 51.5% | +0.0 pp | 51.0% | 2.0% | 4.0% |
| train_rft_r1 | 200 | 32.5% | 35.0% | +0.0 pp | 34.7% | 7.5% | 14.5% |
| train_rft_r1_reject | 200 | 57.5% | 59.5% | +0.0 pp | 60.2% | 0.5% | 2.5% |
| train_sft | 200 | 56.5% | 59.0% | +0.0 pp | 59.2% | 0.5% | 1.0% |
| train_sft_pruned | 200 | 54.5% | 57.0% | +0.0 pp | 57.6% | 0.0% | 2.0% |
| train_sft_seed1 | 200 | 57.0% | 59.5% | +0.0 pp | 59.7% | 0.5% | 1.0% |
| train_sft_seed2 | 200 | 56.5% | 59.0% | +0.0 pp | 59.2% | 0.5% | 1.0% |

## Per-tier (easy 70 / medium 87 / hard 43 on the 200-row set)

| config | easy v1 | easy v2 | medium v1 | medium v2 | hard v1 | hard v2 | monotone easy>=med>=hard? |
|---|---|---|---|---|---|---|---|
| deepseek-v4p1-flash_v1_plain_n200 | 44.3% | 51.4% | 54.0% | 57.5% | 46.5% | 46.5% | NO |
| glm-5p3-flash_v1_plain_n200 | 48.6% | 54.3% | 60.9% | 63.2% | 62.8% | 62.8% | NO |
| glm-5p3_v1_plain_n100 | 34.3% | 34.3% | 60.5% | 60.5% | 45.5% | 45.5% | NO |
| gold_v1_plain_n200 | 100.0% | 100.0% | 100.0% | 100.0% | 100.0% | 100.0% | yes |
| harness_plain_rdefault | 47.1% | 52.9% | 56.3% | 60.9% | 53.5% | 53.5% | NO |
| harness_plain_rdefault_s1 | 47.1% | 51.4% | 58.6% | 60.9% | 55.8% | 58.1% | NO |
| harness_plain_rdefault_s2 | 45.7% | 50.0% | 56.3% | 58.6% | 55.8% | 55.8% | NO |
| harness_prune_repair1 | 44.3% | 51.4% | 52.9% | 55.2% | 41.9% | 46.5% | NO |
| harness_repair1 | 42.9% | 48.6% | 57.5% | 59.8% | 46.5% | 53.5% | NO |
| harness_repair1_fewshot | 42.9% | 48.6% | 60.9% | 63.2% | 48.8% | 55.8% | NO |
| harness_repair1_rdefault | 45.7% | 51.4% | 58.6% | 62.1% | 53.5% | 53.5% | NO |
| harness_repair1_rdefault_s1 | 42.9% | 48.6% | 60.9% | 62.1% | 53.5% | 53.5% | NO |
| harness_repair1_rdefault_s2 | 47.1% | 51.4% | 59.8% | 63.2% | 53.5% | 53.5% | NO |
| harness_route_big | 44.3% | 51.4% | 60.9% | 63.2% | 60.5% | 62.8% | NO |
| harness_route_big_s1 | 45.7% | 51.4% | 56.3% | 58.6% | 51.2% | 53.5% | NO |
| harness_route_big_s2 | 41.4% | 50.0% | 59.8% | 62.1% | 48.8% | 51.2% | NO |
| harness_route_big_s3 | 41.4% | 48.6% | 58.6% | 60.9% | 46.5% | 51.2% | NO |
| harness_route_big_u | 42.9% | 48.6% | 56.3% | 59.8% | 51.2% | 51.2% | NO |
| harness_route_big_u_rdefault | 40.0% | 47.1% | 55.2% | 56.3% | 58.1% | 58.1% | NO |
| harness_validate_only | 42.9% | 47.1% | 54.0% | 56.3% | 44.2% | 48.8% | NO |
| harness_vote3 | 44.3% | 50.0% | 56.3% | 59.8% | 55.8% | 60.5% | NO |
| harness_vote3_rdefault | 41.4% | 48.6% | 57.5% | 59.8% | 58.1% | 58.1% | NO |
| harness_vote3_s1 | 47.1% | 52.9% | 57.5% | 59.8% | 55.8% | 55.8% | NO |
| harness_vote3_s2 | 42.9% | 50.0% | 55.2% | 57.5% | 48.8% | 51.2% | NO |
| kimi-k3_v1_plain_n100 | 40.0% | 42.9% | 62.8% | 62.8% | 36.4% | 36.4% | NO |
| train_base | 34.3% | 38.6% | 58.6% | 62.1% | 51.2% | 51.2% | NO |
| train_rft_r1 | 21.4% | 25.7% | 42.5% | 44.8% | 30.2% | 30.2% | NO |
| train_rft_r1_reject | 50.0% | 54.3% | 60.9% | 62.1% | 62.8% | 62.8% | NO |
| train_sft | 48.6% | 52.9% | 60.9% | 63.2% | 60.5% | 60.5% | NO |
| train_sft_pruned | 48.6% | 52.9% | 59.8% | 62.1% | 53.5% | 53.5% | NO |
| train_sft_seed1 | 47.1% | 51.4% | 63.2% | 65.5% | 60.5% | 60.5% | NO |
| train_sft_seed2 | 48.6% | 52.9% | 62.1% | 64.4% | 58.1% | 58.1% | NO |

Monotone (easy >= medium >= hard) under v2: **1 of 32 configs**.

Skipped: claude-opus-5_v1_plain_n100.json (dead run: no predictions), coverage_curve.json

