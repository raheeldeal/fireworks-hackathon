# Calibration: does vote agreement predict correctness?

Each row: three glm-5p3-flash generate-and-repair chains at temperature 0.7. Agreement = how many chains returned the same result set (score.py multiset rule). Accuracy is for the small model's own voted answer, before any escalation. Source: every vote3 / route run in `results/harness_*.json`.

## Pooled over 5 runs (1000 row-runs)

| agreement | row-runs | share | small-model accuracy |
|---|---|---|---|
| 3/3 | 698 | 69.8% | 61.7% |
| 2/3 | 240 | 24.0% | 35.0% |
| none | 62 | 6.2% | 17.7% |

When escalated, glm-5p3 (default reasoning, generate-and-repair) versus the small model's own answer on the same rows:

| agreement when escalated | row-runs | small-model accuracy | glm-5p3 accuracy |
|---|---|---|---|
| 2/3 | 105 | 33.3% | 25.7% |
| none | 35 | 20.0% | 25.7% |

## Per run

## From `route_big` (200 rows, three glm-5p3-flash repair chains at T=0.7, reasoning low)

| agreement | rows | share | accuracy of small-model voted answer |
|---|---|---|---|
| 3/3 | 147 | 73.5% | 57.8% |
| 2/3 | 41 | 20.5% | 48.8% |
| none | 12 | 6.0% | 16.7% |

On the 12 escalated rows: small-model fallback answer 16.7% correct, glm-5p3 answer 41.7% correct.

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
