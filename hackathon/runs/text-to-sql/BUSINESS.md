# Business model: self-serve analytics ("ask your warehouse in English")

**Who pays.** BI / analytics vendors and internal data platform teams that let business users ask questions of a warehouse in plain English. The expensive failure is not a crash, it is a query that *runs* and returns a plausible wrong number; someone eventually notices and an analyst re-does the work.

**Workload assumption.** A mid-size SaaS analytics product: 2,000 business users × 25 questions/day = **50,000 questions/day, 1.5M/month**. Each wrong answer costs ~10 analyst minutes to catch, re-query and re-send (a conservative figure; wrong numbers that reach a decision cost far more).

**Numbers below are measured on the 180-question Spider test set (execution accuracy, 20 schemas), single run unless noted; monthly $ = measured $ per 1k requests × 1,500 (prompt ≈ 350 tokens incl. schema).**

| config | exec accuracy | $/1k req | inference $/month | wrong answers/month | analyst hours/month |
|---|---|---|---|---|---|
| **glm-5p3-flash, plain prompt (best small)** | **85.4% ± 1.7 (4 runs)** | $0.10 | **$155** | **219,000** | **36,500** |
| glm-5p3-flash → glm-5p3 route (escalate invalid) | 83.9% | $0.14 | $208 | 241,650 | 40,275 |
| kimi-k3, plain prompt (frontier open) | 78.0% ± 1.0 (3 runs, 100 rows) | $2.78 | $4,170 | 334,500 | 55,750 |
| gpt-oss-120b, plain | 77.2% | $0.08 | $122 | 341,700 | 56,950 |
| glm-5p3, plain (large) | 75.0% ± 1.1 (3 runs) | $0.38 | $577 | 358,350 | 59,725 |
| deepseek-v4p1-flash, plain | 74.4% | $0.41 | $613 | 383,400 | 63,900 |
| nemotron-30b-a3b no-think → glm-5p3-flash route | 73.9% | $0.03 | $45 | 391,650 | 65,275 |
| nemotron-30b-a3b, rubric, no-think (cheapest useful) | 70.6% | $0.03 | $48 | 441,600 | 73,600 |
| nemotron-30b-a3b, plain, no-think | 69.4% | $0.015 | $23 | 458,400 | 76,400 |
| Muse Glimmer 30B LoRA SFT (see RESULTS.md) | see RESULTS.md | | | | |

**The one-sentence value claim.** On this task the cheapest good model is also the most accurate: glm-5p3-flash answers 85% of questions correctly at $155/month, versus kimi-k3 at 78% and $4,180/month, so switching saves about $4,000/month in inference *and* removes roughly 115,000 wrong answers a month (about 19,000 analyst hours at 10 minutes each).

**What the numbers say about where value lives.** Inference cost is noise next to error cost at this workload: the gap between the cheapest and the most expensive config is $4,000/month, while one accuracy point is 15,000 wrong answers/month (2,500 analyst hours). Any intervention that buys accuracy, even at 10× the inference price, pays for itself; this is why the pitch is about accuracy per dollar, not dollars.

**Latency.** glm-5p3-flash p50 1.1 s / p95 3.4 s; nemotron no-think p50 0.28 s; kimi-k3 p50 2.3 s / p95 5.3 s. All acceptable for an interactive "ask a question" UI; the no-think small model is the only one fast enough for autocomplete-style use.
