# Business model: product listing → strict JSON

**Who pays:** marketplace and catalogue teams (aggregators, price-comparison engines, retail-media platforms) that turn seller-written listings into filterable, priceable attributes. Each wrong attribute is a lost filter match or a mispriced SKU; each invalid JSON is a pipeline exception a person has to clear.

**Workload assumption:** 500,000 listings/day = 15M calls/month, ≈350 input + ≈250 output tokens per call (output includes hidden reasoning tokens, which Fireworks bills). Costs below are measured $/1k on the locked test set × 15,000.

| configuration | all-fields accuracy | invalid rate | $/1k | monthly cost | wrong rows / month | invalid rows (manual exceptions) / month |
|---|---|---|---|---|---|---|
| glm-5p3-flash, plain prompt (baseline) | 76.5% | 1.5% | $0.176 | $2,640 | 3,525,000 | 225,000 |
| glm-5p3-flash, rubric | 93.0% | 1.0% | $0.223 | $3,345 | 1,050,000 | 150,000 |
| glm-5p3-flash, rubric + JSON-schema mode | 93.5% | 0.0% | $0.223 | $3,345 | 975,000 | 0 |
| **glm-5p3-flash, rubric + 5-shot (best small)** | **95.5%** | 1.0% | **$0.354** | **$5,310** | **675,000** | 150,000 |
| deepseek-v4p1-flash, plain | 78.5% | 0.5% | $0.513 | $7,695 | 3,225,000 | 75,000 |
| glm-5p3 (large), plain | 70.0% | 2.0% | $1.833 | $27,495 | 4,500,000 | 300,000 |
| kimi-k3 (frontier), plain | 69.0% | 0.0% | $4.681 | $70,215 | 4,650,000 | 0 |
| kimi-k3 (frontier), rubric | 92.0% | 4.0% | $5.092 | $76,380 | 1,200,000 | 600,000 |

Latency: best small config p50 1.4 s / p95 3.1 s vs. frontier rubric p50 3.0 s / p95 6.7 s (serverless, shared account under load).

**Value claim (one sentence):** At 500k listings a day, the prompted 30B-class model extracts attributes with 95.5% all-fields accuracy for $5.3k a month, which is 525,000 fewer wrong listings a month and $71k a month less than the frontier model on the same rubric, at half the latency.

**Recommended production configuration:** rubric + 5-shot with JSON-schema mode enabled (schema mode removed all invalid outputs at no extra cost in the rubric test; the combination was not run tonight because of the spend cap, expected ≈95.5% with ~0 invalid).

**What is not in these numbers:** prompt caching (the 5-shot prompt is ~1,000 tokens of fixed prefix, so cached-input pricing would cut the best config's cost roughly in half), volume discounts, and the ~2% of test rows where the gold label itself is debatable (see RESULTS.md misses).
