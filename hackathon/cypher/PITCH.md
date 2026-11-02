# Pitch: 3 minutes

## Slide 1 — The question (20s)
"An analyst asks: *which customers bought from more than three categories?* Someone has to write the graph query. We asked: can an open model do it, and how would you ever know it got it right?"

Say: the only honest grader is the database. Run the query. Compare the rows.

## Slide 2 — What we built (30s)
A text-to-Cypher system plus the benchmark to judge it:
- 200 questions from Neo4j's public set, five real graphs, every answer key verified by executing it live. Hash-locked.
- Harness: validate → generate → execute → repair from the error → three attempts → route on disagreement.
- Fine-tuned a 30B open model on execution-verified data. SFT, then RFT with execution as the reward.
- Every step traced: tokens, cost, latency, the exact query, the rows.

## Slide 3 — Finding 1: price does not buy accuracy (40s)
| Model | Accuracy | Cost / 1k |
|---|---|---|
| kimi-k3 | 50.0% | $6.36 |
| glm-5p3 (large) | 49.0% | $3.13 |
| **glm-5p3-flash (small)** | **60.5%** | **$0.24** |

"26 times cheaper, ten points better. We tried hard to disprove it: rebuilt the scorer, allowed richer answers, turned the big models' reasoning down. The gap held every time."

## Slide 4 — Finding 2: fine-tuning on execution reward (30s)
30B open model: **51.5% → 59.0% (SFT) → 60.0% (RFT)**. Training free. Reward = the query's rows match gold.
Honest footnote: the advantage-weighted RFT variant regressed to 36.5%; no trust region in the API's weighted loss, empty results went 1% → 14.5%. We diagnosed it and switched to rejection sampling.

## Slide 5 — Finding 3: the benchmark everyone uses is 15% mis-keyed (40s)
We hand-audited 40 failures (all 36 easy-tier plus 4 medium). The model is genuinely wrong **twice**.
- 11 broken answer keys ("first 3 orders" → the same order three times; "where is this user" → a tweet)
- 7 ambiguous questions
- 20 cases where the model answered the question and the key returned a different column

"You cannot see this without executing every query. Our corrected scorer and the per-question evidence are in the repo."

## Slide 6 — The product decision (20s)
Accuracy alone is not shippable at 60%. Our three executed attempts give a free confidence signal:
- Answer everything: 55.5% correct.
- **Answer only when all three agree: 69% of questions, 64.8% correct, rest flagged.**
"An analyst can live with 'I don't know'. They cannot live with a confident wrong number in a board deck."

## Demo (live, 30s)
One question. Watch the trace: schema → query → **execution fails, "Variable o not defined"** → repair → 29 correct rows, 2.6s, $0.0009. Then the same question to the expensive model: confident, wrong.

## Close (10s)
"Cheapest model, best accuracy, trained for free on data the database itself verified, with a confidence dial and a corrected benchmark we're giving back. Everything reproduces from the repo; the exam's fingerprint is in it."

---
## Q&A ammunition
- *Why is the small model better?* We don't claim a mechanism. We ruled out scorer strictness, column tolerance and reasoning budget, on identical questions. It reproduces across three expensive models.
- *60% is low.* It is, and the benchmark's own 15% defect rate is part of that. The coverage dial is how you ship at this accuracy.
- *Is the test set clean?* Public test split only, hash-locked, re-verified every run, 500 training rows from the train split with zero overlap, checked by script.
- *Did the harness help?* Not on accuracy. Broken queries 2.2% → 0.1%, plus the confidence signal. We report that plainly.
- *Deployment?* Model trained and saved (`cypher-sft-1150`); dedicated serving not run, no credits. Costs for the 30B rows are sampler prices, flagged in the results.
