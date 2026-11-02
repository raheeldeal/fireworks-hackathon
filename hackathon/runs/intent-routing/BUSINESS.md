# BUSINESS.md: banking intent routing

**Workload assumption:** a mid-size neobank receives 50,000 inbound support messages per day (chat + email), each classified once at arrival to route it to a queue or a self-serve answer. That is 1.5M classifications per month.

**Cost of a misroute:** a misrouted message is re-triaged by a human (1 to 3 minutes of agent time; we use 2 min at $30/h fully loaded = $1.00) and the customer waits longer.

## Monthly cost and errors per configuration (1.5M requests/month)
Model $/month = ($/1k) x 1,500. Errors/month = 1,500,000 x (1 - accuracy). Re-triage $/month = errors x $1.00. Accuracies for rows marked * are on the 100-row subset kimi-k3 saw (the only like-for-like frontier comparison); others on all 154 rows.

| config | accuracy | $/1k | model $/month | errors/month | re-triage $/month | p50 latency |
|---|---|---|---|---|---|---|
| kimi-k3 frontier, plain | 88.0%* | 5.60 | 8,397 | 180,000 | 180,000 | 1.8 s |
| glm-5p3 large, plain | 83.8% | 2.88 | 4,322 | 243,000 | 243,000 | 1.1 s |
| deepseek-v4p1-flash, plain | 83.8% | 0.66 | 983 | 243,000 | 243,000 | 1.3 s |
| gpt-oss-120b, plain | 84.4% | 0.28 | 422 | 234,000 | 234,000 | 0.5 s |
| glm-5p3-flash small, plain (best small) | 85.1% (83.6% mean over orders) | 0.26 | 389 | 223,500 | 223,500 | 1.2 s |
| nemotron small, rubric, no think (cheapest) | 77.3% | 0.12 | 177 | 340,500 | 340,500 | 0.3 s |
| **routing: glm-flash no-think → kimi-k3 @0.70** | **88.0%*** | **1.74** | **2,606** | **180,000** | 180,000 | 0.67 s |
| routing: glm-flash no-think → gpt-oss @0.70 | 84.4% | 0.30 | 450 | 234,000 | 234,000 | 0.67 s |

Reading the table honestly: model spend is small next to re-triage cost at every configuration. The decision that moves money is accuracy, and the accuracy spread between the cheapest sensible option and the frontier is about 4 points = 60,000 misroutes/month ≈ $60k/month of agent time. Within that, routing lets you buy frontier accuracy for $2.6k/month instead of $8.4k/month.

## One-sentence value claim
Routing a $0.23-per-1k small model with confidence-based escalation to the frontier model matches the frontier's 88% accuracy on 77 banking intents while sending only 27% of traffic upstream, cutting model spend from $8.4k to $2.6k per month at 1.5M messages (69% saving, $5.8k/month) with no increase in misroutes and p50 latency down from 1.8 s to 0.7 s.

## Caveats
- Frontier comparison is on 100 rows; ±1 point = 1 message. Seed spread on 154 rows is ±2.6 points. Treat all sub-3-point differences as ties.
- Re-triage cost assumes every misroute is caught by a human; in practice some are caught by the customer re-asking, which costs more in satisfaction than in dollars.
- Serving a fine-tuned LoRA would need a dedicated deployment (per GPU-hour), so the SFT row (not run; training slot busy all night) is not in the cost table.
