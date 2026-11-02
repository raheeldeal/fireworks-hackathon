# Pitch: function calling (3 minutes)

**1. Problem and who pays (20s).** Every LLM agent product turns user requests into API calls. A wrong tool or a wrong argument is a wrong action: the wrong date booked, the wrong record edited. So teams route every tool call through a frontier model and pay frontier prices for a narrow job. At 1M calls a day on kimi-k3 that is about $95,000/month.

**2. Task and eval (20s).** We built a 200-example locked test set from the Berkeley Function Calling Leaderboard v4 (real-world schemas, 1 to 12 tools per request, 60% weighted toward the harder multi-tool categories). Scoring is automatic and strict: right function, every argument right, against BFCL's list of acceptable values. We also report partial credit and invalid outputs, and we measured both the native tools API and plain-prompt JSON.

**3. Baseline (20s).** Off-the-shelf small model (Nemotron 3.5 30B-A3B, default settings): 73.9% strict, and 21% of requests return nothing at all. Frontier open model (Kimi K3): 88.0% at 58x the cost and 5x the latency. That looks like a 14-point gap that only a frontier model or a fine-tune can close.

**4. What we changed (40s).** It was not a capability gap. Two harness settings, no training:
- Turn hidden reasoning off (`reasoning_effort: none`). The baseline's missing answers were the model spending its whole output budget thinking. Reasoning off: 87.0%, 0.38 s, $0.055/1k.
- Force a tool call (`tool_choice: required`). 91.0% strict, zero invalid outputs, same cost.
Then we tested the levers everyone reaches for first: a rubric prompt (no gain, and it hurts when reasoning is on), few-shot (worse), JSON schema output (no gain), confidence routing to a bigger model (nothing to gain, the bigger models are not more accurate), and a LoRA SFT on 394 examples (free Muse Glimmer 30B promotion, Serverless Training API, no deployment needed to score it): 65.5% → 89.5% strict, one epoch, 40 minutes. SFT works, but on this task two API flags get you there first.

**5. Result (40s).** The table. Best small configuration: 91.0% ± 0.5% strict (3 seeds) at $0.054/1k and 0.40 s p50. Frontier: Kimi K3 88.0% at $3.16/1k and 1.85 s; GLM-5.3 90.0% at $1.06/1k. Cheapest frontier-matching model: GLM-5.3-flash 91.5% at $0.151/1k and 0.93 s. The small model is on the frontier of the quality/cost chart.

**6. Business value (20s).** At 1M calls/day: $1,620/month instead of $94,740 (Kimi K3), about 0.9M fewer wrong calls per month, p50 0.40 s instead of 1.85 s. Against GLM-5.3-flash: 64% cheaper, 2.3x faster, accuracy inside seed noise.

**7. How far we pushed it (20s).** The frontier chart. Nine of the 200 rows are missed by every model (dataset conventions: a missing year assumed to be 2023, cents vs dollars, a "details:" prefix), so the ceiling is about 95% and the small model is within 4 points of it. Where it still fails: live multi-tool requests with 8+ tools (81% vs 95% on single-tool), mostly value formatting (extra words copied from the user, 5 vs 0.05) and optional-argument invention. Honest caveat: Nemotron-lightning is deprecated on 2026-11-07, so the recommendation is "the cheapest no-reasoning small model with forced tool choice", measured again on the replacement.

## Slides
1. **Title**: "Right tool, right arguments, 1/58th the cost" + one line task definition.
2. **Table**: config × strict acc × $/1k × p50 (from compare.py), with the 73.9% naive baseline, the 91.0% tuned-harness result, flash, GLM-5.3, Kimi K3.
3. **Diagram**: request → small model (reasoning off, tool_choice required) → tool call; dotted box for the confidence gate to a big model, labelled "measured: not needed".
4. **Business value**: monthly $ and wrong calls per month for small-naive, small-tuned-harness, flash, frontier; plus frontier.png.
