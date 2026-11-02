# Business model: English → regex inside a data-tooling product

**Who pays.** Observability, log-search, ETL and data-validation products (Datadog/Splunk-style query builders, Airbyte/dbt, spreadsheet "extract a pattern" features). Their users write regexes by hand today; each one costs 5 to 15 minutes and is a top source of validation bugs and support tickets.

**Workload assumption.** 50,000 "describe the pattern in English" requests per day = 1.5M per month. One wrong regex = a silent data-quality bug or a support ticket; priced at 10 minutes of an engineer ($15). The $15 figure dominates everything below, so the sensitivity line at the end matters more than the headline.

**Monthly cost and errors per configuration** (from RESULTS.md; cost = $/1k × 1,500; errors = (1 − accuracy) × 1.5M):

| configuration | accuracy | $/1k | $/month inference | wrong regexes / month | error cost / month ($15 each) |
|---|---|---|---|---|---|
| glm-5p3-flash, plain prompt (where most teams would start) | 68.0% | 0.0277 | $42 | 480,000 | $7.2M |
| glm-5p3-flash, 5-shot | 86.5% | 0.0357 | $54 | 202,500 | $3.0M |
| **glm-5p3-flash, rubric prompt (best small)** | **95.0%** | **0.1241** | **$186** | **75,000** | **$1.13M** |
| muse-glimmer-30b + free LoRA, plain prompt (sampler pricing) | 93.5% | 0.2003 | $300 | 97,500 | $1.46M |
| glm-5p3-flash rubric → glm-5p3 rubric, route at 0.9 | 96.0% | 0.3021 | $453 | 60,000 | $0.90M |
| glm-5p3, rubric prompt | 95.5% | 1.1488 | $1,723 | 67,500 | $1.01M |
| kimi-k3, rubric prompt (frontier) | 96.0% | 2.6370 | $3,956 | 60,000 | $0.90M |

**One-sentence value claim.** At 50k requests a day, the rubric-prompted small model serves the feature for $186 a month instead of $3,956 for the frontier model, with the same accuracy within noise (95.0% vs 96.0%, one or two test rows), and it cuts wrong regexes from 480,000 to 75,000 a month compared with the plain-prompt baseline a team would ship first.

**What actually moves money.** Inference is a rounding error next to error cost at this price per mistake: the whole frontier bill ($3,956) is worth 264 avoided errors. So the 27-point harness gain (405,000 fewer wrong regexes a month, $6M at $15 each) is the business result; the model choice is a $3,770-a-month saving on top of it. Routing at 0.9 is the only configuration that beats the small model on paper (+1 point, +$267 a month) and the +1 point is within seed noise, so it is not a claim I would make to a customer.

**Sensitivity.** At $1 per wrong regex (a quick retry by the user, no bug) the error column drops to $75k vs $60k and the inference gap of $3,770 a month is 25% of the total; the small model still wins. The frontier only pays for itself if a wrong regex costs more than about $250 AND the 1-point gap is real, which this test set cannot establish.

**Latency.** A regex suggestion sits in an interactive editor; p50 under 1 s keeps it feeling instant. glm-5p3-flash with the rubric prompt is 0.57 s p50 / 0.96 s p95; kimi-k3 is 1.01 s p50 / 3.73 s p95, which is a visible pause.
