# Business value

## The buyer
Analyst teams querying graph databases: fraud rings, supply-chain exposure, identity resolution, knowledge graphs. Today a question like "which suppliers share a bank account with a flagged entity?" goes into a ticket queue and an engineer writes Cypher. Median wait: hours to days.

## Workload assumption
2,000 analyst questions per day (a 40-person analytics org, ~1 question per analyst per hour).

## Cost per correct answer
The metric that matters is not price per call, it is price per *correct* answer, because a wrong answer costs more than it saves.

| Setup | Accuracy | $ / 1k questions | $ per correct answer | $ / month at 2k/day |
|---|---|---|---|---|
| kimi-k3 (priciest open) | 50.0% | $6.36 | $0.0127 | $382 |
| glm-5p3 (large) | 49.0% | $3.13 | $0.0064 | $188 |
| **glm-5p3-flash (small)** | **60.5%** | **$0.24** | **$0.0004** | **$14** |
| 30B + SFT + RFT (ours) | 60.0% | $0.25 (served) | $0.0004 | $15 |

**The frontier premium buys nothing.** Paying 26x more per call delivers 10 points *less* accuracy on this task. At 2,000 questions a day that is $368/month of pure waste, and the cheap model is the better product.

## The number that actually sells
Wrong answers reaching the analyst, per 1,000 questions:

| Setup | Answers given | Wrong answers delivered |
|---|---|---|
| Expensive model, answers everything | 1,000 | 500 |
| Our model, answers everything | 1,000 | 395 |
| **Our model + confidence dial (3/3 agreement)** | **692** | **244**, and 308 flagged for review |

An analyst can act on "I don't know". They cannot act on a confident wrong number that reaches a board deck. The confidence dial is what makes a 60%-accuracy system shippable: it converts silent errors into an explicit review queue.

## Analyst time
A query an engineer would take 20 minutes to write returns in ~2 seconds. At 692 auto-answered questions per 1,000, that is roughly 230 engineer-hours saved per 1,000 questions, against 103 questions sent to review.

## What it costs to run
$14 per month of inference at this workload. Fine-tuning was free (Fireworks free tier, under 16B / promotional base). The expensive line item is not the model, it is the engineer the model replaces.
