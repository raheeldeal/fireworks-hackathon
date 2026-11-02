# Calibration: does vote agreement predict correctness?

Each row: three glm-5p3-flash generate-and-repair chains at temperature 0.7. Agreement = how many chains returned the same result set (score.py multiset rule). Accuracy is for the small model's own voted answer, before any escalation. Source: every vote3 / route run in `results/harness_*.json`.

## Pooled over 10 runs (2000 row-runs)

| agreement | row-runs | share | small-model accuracy |
|---|---|---|---|
| 3/3 | 1388 | 69.4% | 61.1% |
| 2/3 | 479 | 23.9% | 33.0% |
| none | 133 | 6.7% | 20.3% |

When escalated, glm-5p3 (default reasoning, generate-and-repair) versus the small model's own answer on the same rows:

| agreement when escalated | row-runs | small-model accuracy | glm-5p3 accuracy |
|---|---|---|---|
| 2/3 | 105 | 33.3% | 25.7% |
| none | 80 | 20.0% | 27.5% |

## Per run

## From `route_big` (200 rows, three glm-5p3-flash repair chains at T=0.7, reasoning low)

| agreement | rows | share | accuracy of small-model voted answer |
|---|---|---|---|
| 3/3 | 147 | 73.5% | 57.8% |
| 2/3 | 41 | 20.5% | 48.8% |
| none | 12 | 6.0% | 16.7% |

On the 12 escalated rows: small-model fallback answer 16.7% correct, glm-5p3 answer 41.7% correct.

## From `route_big_s1` (200 rows, three glm-5p3-flash repair chains at T=0.7, reasoning low)

| agreement | rows | share | accuracy of small-model voted answer |
|---|---|---|---|
| 3/3 | 134 | 67.0% | 59.0% |
| 2/3 | 49 | 24.5% | 34.7% |
| none | 17 | 8.5% | 23.5% |

On the 17 escalated rows: small-model fallback answer 23.5% correct, glm-5p3 answer 41.2% correct.

## From `route_big_s2` (200 rows, three glm-5p3-flash repair chains at T=0.7, reasoning low)

| agreement | rows | share | accuracy of small-model voted answer |
|---|---|---|---|
| 3/3 | 144 | 72.0% | 60.4% |
| 2/3 | 38 | 19.0% | 26.3% |
| none | 18 | 9.0% | 16.7% |

On the 18 escalated rows: small-model fallback answer 16.7% correct, glm-5p3 answer 27.8% correct.

## From `route_big_s3` (200 rows, three glm-5p3-flash repair chains at T=0.7, reasoning low)

| agreement | rows | share | accuracy of small-model voted answer |
|---|---|---|---|
| 3/3 | 137 | 68.5% | 60.6% |
| 2/3 | 53 | 26.5% | 30.2% |
| none | 10 | 5.0% | 20.0% |

On the 10 escalated rows: small-model fallback answer 20.0% correct, glm-5p3 answer 10.0% correct.

## From `route_big_u` (200 rows, three glm-5p3-flash repair chains at T=0.7, reasoning low)

| agreement | rows | share | accuracy of small-model voted answer |
|---|---|---|---|
| 3/3 | 137 | 68.5% | 59.9% |
| 2/3 | 53 | 26.5% | 30.2% |
| none | 10 | 5.0% | 10.0% |

On the 63 escalated rows: small-model fallback answer 27.0% correct, glm-5p3 answer 30.2% correct.

## From `route_big_u_rdefault` (200 rows, three glm-5p3-flash repair chains at T=0.7, reasoning default)

| agreement | rows | share | accuracy of small-model voted answer |
|---|---|---|---|
| 3/3 | 135 | 67.5% | 65.9% |
| 2/3 | 52 | 26.0% | 36.5% |
| none | 13 | 6.5% | 30.8% |

On the 65 escalated rows: small-model fallback answer 35.4% correct, glm-5p3 answer 18.5% correct.

## From `vote3` (200 rows, three glm-5p3-flash repair chains at T=0.7, reasoning low)

| agreement | rows | share | accuracy of small-model voted answer |
|---|---|---|---|
| 3/3 | 140 | 70.0% | 58.6% |
| 2/3 | 46 | 23.0% | 39.1% |
| none | 14 | 7.0% | 28.6% |

## From `vote3_rdefault` (200 rows, three glm-5p3-flash repair chains at T=0.7, reasoning default)

| agreement | rows | share | accuracy of small-model voted answer |
|---|---|---|---|
| 3/3 | 139 | 69.5% | 66.9% |
| 2/3 | 48 | 24.0% | 22.9% |
| none | 13 | 6.5% | 0.0% |

## From `vote3_s1` (200 rows, three glm-5p3-flash repair chains at T=0.7, reasoning low)

| agreement | rows | share | accuracy of small-model voted answer |
|---|---|---|---|
| 3/3 | 135 | 67.5% | 62.2% |
| 2/3 | 49 | 24.5% | 36.7% |
| none | 16 | 8.0% | 31.2% |

## From `vote3_s2` (200 rows, three glm-5p3-flash repair chains at T=0.7, reasoning low)

| agreement | rows | share | accuracy of small-model voted answer |
|---|---|---|---|
| 3/3 | 140 | 70.0% | 60.0% |
| 2/3 | 50 | 25.0% | 26.0% |
| none | 10 | 5.0% | 20.0% |
