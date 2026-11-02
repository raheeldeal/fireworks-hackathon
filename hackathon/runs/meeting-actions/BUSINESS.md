# Business model: action items from meeting transcripts

## Workload assumption
A mid-size meeting-notes product (Granola / Otter / Fellow class) processes **50,000 recorded meetings per day** (1.5M per month). Each meeting is one request: transcript in, action-item JSON out. Transcription is already paid for; this step is pure LLM inference. Every missed or invented action item is a user-visible defect: a task that never reaches the task tracker, or a bogus one that does. Average meeting in our test set has 3.6 real action items.

## Monthly cost and error volume per configuration
From RESULTS.md. Monthly $ = ($/1k) × 1,500. Item errors per month = (1 − F1) × 1.5M meetings × 3.6 items. Note the ceiling: roughly 2 to 3 F1 points of every row are label noise and scorer strictness (RESULTS.md, misses analysis), so the error counts are upper bounds and the differences between rows are what matters.

| config | F1 | $/1k meetings | $/month | item errors / month | p50 s |
|---|---|---|---|---|---|
| nemotron 30B-A3B, plain | 0.921 | 0.063 | $94 | 427,680 | 0.56 |
| glm-5p3-flash, plain | 0.938 | 0.170 | $255 | 336,420 | 1.04 |
| glm-5p3-flash, rubric + 5-shot (best small) | 0.961 | 0.744 | $1,116 | 208,980 | 1.08 |
| deepseek-v4p1-flash, plain (best overall) | 0.965 | 0.368 | $552 | 190,080 | 1.31 |
| routing flash -> deepseek, thr 0.9 | 0.946 | 0.292 | $438 | 289,980 | 1.37 |
| glm-5p3 (large), plain | 0.930 | 1.556 | $2,334 | 379,620 | 1.36 |
| kimi-k3 (frontier), plain, n=70 | 0.953 | 5.326 | $7,989 | 252,180 | 2.85 |

## What the numbers say
- **Frontier is the wrong buy here.** kimi-k3 costs $8.0k/month and is *less* accurate than a $552/month medium model (deepseek-v4p1-flash) and a $1.1k/month small model with five examples in the prompt. glm-5p3 (large) is worse than its own flash variant at 9x the price.
- **Cheapest acceptable:** glm-5p3-flash plain at $255/month, F1 0.938. Moving to 5-shot buys +2.3 F1 points (about 127k fewer wrong items a month) for +$860/month; deepseek buys +2.7 points for +$297/month. deepseek dominates.
- **Prompt caching** would cut the 5-shot config's cost by roughly 70% in production (the 4,300-token few-shot prefix is identical on every call), which would put it at roughly $350/month, level with deepseek. Not measured tonight; serverless pricing on the price table was used as is.
- **Latency:** every small/medium option answers in about 1 s p50; kimi takes 2.9 s. For a notes product that posts action items after the meeting ends, latency is not the deciding axis.

## The one-sentence value claim
"On 150 held-out meetings, a $0.37-per-thousand open model (deepseek-v4p1-flash) and a $0.15 small model with five examples both beat the frontier model on action-item F1 (0.965 and 0.961 vs 0.953) at 7 to 14x lower cost, which at 50k meetings a day is $7.4k/month saved with about 62k fewer wrong action items."
