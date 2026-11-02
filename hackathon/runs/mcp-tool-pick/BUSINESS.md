# Business model: tool routing for an agent gateway

**Workload assumption:** a mid-size copilot or MCP gateway with 50k daily active users × 20 turns = 1,000,000 routing decisions per day, 30M per month. Every turn starts with "which of our 100 tools?", and the catalog is re-sent on every call.

**Who pays:** the platform team running the gateway. A wrong pick is either a wasted round-trip (the agent calls the wrong tool, sees the error, retries: +1 model call and +1 to 3 s) or, worse, a wrong side-effect (an email sent instead of drafted, an event deleted instead of updated).

## Monthly cost and errors per configuration (30M calls)

| configuration | accuracy | $/1k | $/month | wrong picks / month | p50 latency |
|---|---|---|---|---|---|
| kimi-k3 (frontier, plain) | 95.0% | 6.150 | $184,500 | 1,500,000 | 1.52 s |
| glm-5p3 (large, plain) | 95.6% | 2.744 | $82,300 | 1,320,000 | 0.92 s |
| deepseek-v4p1-flash (plain) | 98.9% | 0.589 | $17,700 | 330,000 | 0.86 s |
| gpt-oss-120b (plain) | 92.8% | 0.296 | $8,900 | 2,160,000 | 0.42 s |
| **glm-5p3-flash (plain), chosen** | **98.3%** | **0.284** | **$8,500** | **510,000** | **0.81 s** |
| route nemotron(no reasoning) -> glm-5p3-flash, 33% escalated | 97.2% | 0.184 | $5,500 | 840,000 | 0.33 s |
| nemotron, no reasoning (plain) | 86.1% | 0.087 | $2,600 | 4,170,000 | 0.24 s |
| catalog-free LoRA on a small model (not run; estimate) | ≥98% target | ~0.03 | ~$900 | ~500,000 | ~0.3 s |

Errors per month = 30M × (1 − accuracy). Costs are measured token counts × the PROTOCOL serverless price table; the fine-tune row assumes ~90 input + 5 output tokens per call at glm-5p3-flash prices and is an estimate, not a measurement.

## Where the money goes
82% of each glm-5p3-flash call is the catalog (about 1,560 of 1,650 input tokens). Shrinking the catalog with keyword retrieval (top-10) cut the cost per call by 55% but dropped accuracy to 70%, because 30% of requests share no keyword with their tool's description. The only intervention that removes the catalog *without* losing the tool is to train it into the model, which is why the fine-tune row is the one worth building next.

## The one-sentence value claim
At 1M routing calls a day, glm-5p3-flash picks the right tool more often than the frontier model (98.3% vs 95.0%) for $8.5k instead of $184k a month, saving about $176k a month and 1M wrong tool calls, at half the latency; a catalog-free fine-tune would cut the remaining $8.5k to about $1k.

## Caveats
- Synthetic requests written by glm-5p3; real user requests are messier (multi-tool, missing context), so absolute accuracies are optimistic. The ranking between models is the more reliable finding.
- kimi-k3 was scored on 100 of the 180 rows (budget cap).
- Latencies were measured with ten agents sharing the account and 4 concurrent workers; p95 values are pessimistic.
