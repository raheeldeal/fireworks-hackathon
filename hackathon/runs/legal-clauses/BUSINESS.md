# Business model: clause classification for contract lifecycle management

**Who pays.** CLM vendors (Ironclad, DocuSign CLM, Agiloft) and in-house legal-ops teams tag every clause of every incoming contract so lawyers can search by provision, run playbook checks ("every vendor contract must have a Limitation of Liability clause") and flag non-standard terms. Today it is a mix of paralegal review and keyword rules.

**Workload assumption.** A mid-size CLM customer ingests 2,000 contracts/day with ~60 clauses each: 120,000 clause classifications/day, **3.6M per month**.

| configuration | accuracy | $/1k | $/month | misclassified clauses/month |
|---|---|---|---|---|
| nemotron 3.5 30B, no-think (cheapest) | 56.8% | 0.125 | $449 | 1,555,920 |
| glm-5p3-flash + JSON mode (best small, 3 seeds) | 68.8% | 0.362 | $1,305 | 1,123,200 |
| deepseek-v4p1-flash, no-think (medium) | 68.8% | 0.704 | $2,534 | 1,121,760 |
| glm-5p3, no-think (large) | 66.3% | 3.315 | $11,934 | 1,212,120 |
| kimi-k3, no-think (frontier, 80 rows) | 73.8% | 7.244 | $26,080 | 944,999 |
| Muse Glimmer 30B LoRA SFT, 330-token prompt (eval-path sampling price) | 68.8% | 0.959 | $3,452 | 1,123,200 |

Costs are serverless list prices from PROTOCOL.md times measured tokens (the 100-label prompt is ~2.7k tokens per call; the fine-tuned model's prompt is 330 tokens because the labels live in the weights). The SFT row's $/1k is the serverless-training sampling rate we actually paid ($1.96/M prefill, $4.88/M sample); production serving would be a dedicated deployment priced per GPU-hour, which at 120k calls/day is amortized far below the kimi line, and its 480-token requests are 6x smaller than the prompt-only ones.

**What an error costs.** A misclassified clause is a provision a lawyer cannot find by filter and a playbook check that silently passes or falsely fails. If a paralegal reviews flagged contracts at 2 minutes per wrongly tagged clause and only 10% of errors surface for review, the best small model's 1.12M errors/month cost ~3,700 paralegal hours/month; every accuracy point is 36,000 fewer wrong tags.

**One-sentence value claim.** On a 199-clause LEDGAR test set, a 30B open model served on Fireworks matches the frontier model's accuracy at 1/20th the cost ($1.3k vs $26k per month at 3.6M clauses), but nothing moves accuracy past ~69% on the full set: the fine-tune ties the best prompt and misses the same 44 clauses, because the remaining errors are near-synonym heading conventions in the dataset itself.
