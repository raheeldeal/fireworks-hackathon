# Business model: function calling

**Workload assumption.** 1,000,000 tool calls per day (a mid-size agent product: ~200k daily sessions × 5 tool calls). Per call ~900 input tokens (system prompt + 2 to 12 tool schemas + request) and 50 to 800 output tokens depending on how much hidden reasoning the model does. 30 days per month = 30M calls/month.

**Formula.** Monthly cost = 30,000 × ($ per 1k requests measured on the test set). Wrong calls per month = 30M × (1 − strict accuracy). The $/1k figures come straight from `results/*.json` (token counts × the PROTOCOL price table), so they include each model's hidden reasoning tokens, which is why nemotron "at default" is not cheap.

**Per-configuration table** (strict accuracy on the locked 200-row test set; kimi-k3 on the first 100 rows).

| configuration | strict acc | $/1k | monthly $ | wrong calls / month | p50 latency |
|---|---|---|---|---|---|
| nemotron-lightning, default reasoning, max_tokens 1024 (naive baseline) | 73.9% | $0.159 | $4,770 | 7.8M | 1.9 s |
| nemotron-lightning, default reasoning, max_tokens 4096 | 88.0% | $0.199 | $5,970 | 3.6M | 2.2 s |
| nemotron-lightning, reasoning off, plain prompt | 87.0% | $0.055 | $1,650 | 3.9M | 0.38 s |
| **nemotron-lightning, reasoning off + tool_choice=required** | **91.0%** | **$0.054** | **$1,620** | **2.7M** | **0.40 s** |
| nemotron (reasoning off) → glm-5p3-flash on low confidence (12% escalated) | 90.0% | $0.074 | $2,220 | 3.0M | 0.41 s |
| glm-5p3-flash (cheapest model that matches the frontier) | 91.5% | $0.151 | $4,530 | 2.6M | 0.93 s |
| Muse Glimmer 30B base, no tuning (sampler rates, accuracy only) | 65.5% | n/a | n/a | 10.4M | n/a |
| Muse Glimmer 30B + LoRA SFT on 394 rows (sampler rates, accuracy only) | 89.5% | n/a | n/a | 3.2M | n/a |
| glm-5p3 (large, reasoning low) | 90.0% | $1.058 | $31,740 | 3.0M | 0.67 s |
| kimi-k3 (frontier open) | 88.0% | $3.158 | $94,740 | 3.6M | 1.85 s |

**The one-sentence value claim.** At 1M tool calls a day, running nemotron-lightning with reasoning off and `tool_choice=required` instead of kimi-k3 saves about $93,000/month (98%), makes roughly 0.9M fewer wrong calls per month (91.0% vs 88.0% strict), and answers in 0.40 s p50 instead of 1.85 s. Against the cheapest frontier-matching model (glm-5p3-flash) it saves $2,900/month (64%) for a 0.5-point accuracy difference that is inside the seed-to-seed noise (see RESULTS.md variance).

**What the numbers do not say.** The locked test set is BFCL, not a customer's tool catalog; 9 of its 200 rows are missed by every model because of dataset conventions (missing year assumed 2023, cents vs dollars, a "details:" prefix), so the real ceiling is about 95%. Nemotron-lightning is scheduled for deprecation on 2026-11-07 per the model endpoint, so the production recommendation is "the cheapest no-reasoning small model with forced tool choice", with nemotron as tonight's instance of it.

**Why a wrong call costs more than a wrong chat answer.** A tool call is an action: a wrong argument books the wrong date or edits the wrong record. Teams therefore pay frontier prices for every call. The finding tonight is that for a fixed tool catalog the task is narrow enough that the small model matches the frontier model once two harness settings are right (no hidden reasoning, forced tool choice), which turns a per-call frontier bill into a per-call small-model bill without a fine-tune.
