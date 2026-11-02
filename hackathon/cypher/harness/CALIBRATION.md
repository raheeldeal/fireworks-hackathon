# Calibration: does vote agreement predict correctness?

## From `vote3` (200 rows, three glm-5p3-flash repair chains at T=0.7)

| agreement | rows | share | accuracy of voted answer |
|---|---|---|---|
| 3/3 | 140 | 70.0% | 58.6% |
| 2/3 | 46 | 23.0% | 39.1% |
| none | 14 | 7.0% | 28.6% |

## From `route_big` (6 rows, three glm-5p3-flash repair chains at T=0.7)

| agreement | rows | share | accuracy of voted answer |
|---|---|---|---|
| 3/3 | 3 | 50.0% | 33.3% |
| 2/3 | 2 | 33.3% | 100.0% |
| none | 1 | 16.7% | 0.0% |

On the 1 escalated rows: small-model fallback answer 0.0% correct, glm-5p3 answer 100.0% correct.
