# BUSINESS: auto-fix on red CI

**Who pays:** an engineering org running a bot that proposes a fix whenever a unit test goes red. A correct fix
saves the developer the interruption; a wrong fix costs review time. Fix quality is exactly what this eval measures:
the hidden tests pass or they do not.

**Workload assumption:** 2,000 eligible failing CI runs per day (small, single-function failures) → **60,000 calls
per month**. A developer interruption costs 20 minutes of a $120/hour loaded engineer = $40 per fix a human would
otherwise make; a wrong proposed fix costs 5 minutes of review = $10.

Monthly inference $ = $/1k × 60. Wrong fixes/month = (1 − accuracy) × 60,000. Clean numbers from RESULTS.md.

| configuration | accuracy | $/1k | inference $/month | wrong fixes / month | review cost of wrong fixes | human-time saved |
|---|---|---|---|---|---|---|
| gpt-oss-120b plain | 79.9% | 0.295 | $18 | 12,060 | $120,600 | $1,917,600 |
| nemotron-lightning plain | 79.3% | 0.476 | $29 | 12,420 | $124,200 | $1,903,200 |
| deepseek-v4p1-flash plain | 96.3% | 0.789 | $47 | 2,220 | $22,200 | $2,311,200 |
| glm-5p3 (large) plain | 96.3% | 4.206 | $252 | 2,220 | $22,200 | $2,311,200 |
| **glm-5p3-flash plain (3 seeds)** | **99.4%** | **0.259** | **$16** | **360** | **$3,600** | **$2,385,600** |
| glm-5p3-flash → glm-5p3, verify-router | 100.0% | 0.370 | $22 | 0 (1 seed) | $0 | $2,400,000 |
| kimi-k3 plain (frontier, 100 rows) | 99.0% | 3.710 | $223 | 600 | $6,000 | $2,376,000 |

**One-sentence value claim:** at 60k fixes a month, the $0.15/M-token glm-5p3-flash matches the frontier model's pass
rate (99.4% vs 99.0%) for $16 instead of $223 of inference, and the verify-and-escalate router removes the last
0.6% of wrong fixes for $6 more per month.

**Honest reading:** the inference line is noise next to the human line (tens of dollars vs millions), so the decision
is driven entirely by pass rate, and every model above 96% is "good enough" for this workload. That is the business
version of the headroom verdict: this task does not discriminate between models well enough to be worth a hackathon.
Where cost does matter is scale: at 2M calls/month (a CI vendor, not one org) the frontier model is $7.4k/month vs
$520 for the small one, and the router's 3% escalation adds $220.
