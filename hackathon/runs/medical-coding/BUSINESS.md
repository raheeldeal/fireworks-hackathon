# Business model (skeleton; numbers filled in after the eval runs)

**Who pays:** revenue-cycle vendors and clinic billing teams. A medical coder costs about $30/hour fully loaded and codes roughly 30 outpatient charts per hour, so about $1 per chart. Each wrong or missing code is a denied, delayed, or under-paid claim; industry rework cost per denied claim is commonly cited around $25 to $120 (MGMA / HFMA estimates).

**Workload assumption:** 50,000 outpatient encounters per day (one mid-size vendor), 1.5M per month.

**Model-assisted flow:** the model pre-codes; a coder reviews. Charts where the model is confident go to a fast review lane; low-confidence charts go to full review.

| configuration | $/1k requests | monthly inference cost | set-F1 | exact-set rate | wrong charts / month (1 - exact) |
|---|---|---|---|---|---|
| pending | | | | | |

**One-sentence value claim:** pending real numbers.
