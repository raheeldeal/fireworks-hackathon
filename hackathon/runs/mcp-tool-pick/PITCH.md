# Pitch: pick the right tool out of 100, 22x cheaper than frontier (3 minutes)

Honest framing first: on this eval the small model already matches or beats the frontier model, so the story is cost and latency, not accuracy. If the real hackathon wants an accuracy delta, this task needs a harder catalog (see RESULTS.md headroom verdict).

## Script

**1. Problem and who pays (20 s).** Every agent turn starts with one question: which tool? Our gateway has 100 MCP tools across 16 servers, and the whole catalog rides along in every call. Wrong pick means a wasted round-trip or a wrong side-effect: an email sent instead of drafted. At a million turns a day, the "which tool" step alone is a six-figure monthly line item if you use a frontier model.

**2. Task and eval (20 s).** Input: one user message plus the catalog. Output: one tool name. We built 500 requests, 5 per tool, in 5 styles from terse to indirect, with deliberately confusable neighbors like calendar.update_event vs reminders.create. 180 are locked as the test set, scored by exact match, with invalid names counted as wrong.

**3. Baseline (20 s).** Frontier open model kimi-k3: 95.0% at $6.15 per thousand calls, 1.5 s. The 30B nemotron at default settings: 82%, and it burned its whole token budget thinking on a sixth of the rows. glm-5p3-flash, plain prompt: 98.3% ± 0.6 over three seeds at $0.28 per thousand, 0.8 s.

**4. What we changed (40 s).** One diagram: request -> small model -> confidence check -> big model only when unsure. We swept 15 harness variants: rubric prompt, 5-shot, JSON mode, ranked lists, reasoning on/off, keyword retrieval of 10 or 20 candidates, and logprob routing at six thresholds between three model pairs. Findings: turning nemotron's reasoning off gave +4 points at 10x lower latency; JSON mode and ranked lists hurt; keyword retrieval capped accuracy at 70% because a third of requests share no words with their tool's description; routing nemotron to flash at logprob < -0.1 kept 97.2% at $0.18 per thousand and 0.33 s median.

**5. Result (40 s).** The table. glm-5p3-flash plain: 98.3%, $0.28/1k, 0.81 s. Frontier: 95.0%, $6.15/1k, 1.52 s. The small model is 3 points better, 22x cheaper, 2x faster. The mid-size deepseek-flash ties it at twice the cost. Prompting could not move flash further: every variant lands within seed noise. The three rows everyone misses are genuinely ambiguous ("the PDF you sent me, where does it live" could be Gmail or Drive).

**6. Business value (20 s).** At 1M calls a day: $8.5k a month instead of $184k, and about a million fewer wrong tool calls a month than the frontier model. 82% of that $8.5k is the catalog tokens.

**7. How far we pushed it (20 s).** The curve: 46 points from $0.09 to $6 per thousand. Cheapest viable point is the routed pair at $0.18 and 97%. The next point is not on the chart: fine-tuning the catalog into a small model so the 1,560 catalog tokens never get sent. Training is free this month on Fireworks; our account could not upload datasets tonight, so that is the first thing to do on hackathon day.

## Slides
1. **Title:** "Which tool? 100 MCP tools, 98% right, $0.28 per thousand." Subtitle: tool routing on Fireworks small models, with the eval and the curve.
2. **Table:** the condensed results table from RESULTS.md (6 baselines, best 4 interventions, best 2 routes, frontier highlighted in red, chosen config in bold).
3. **Diagram:** request -> glm-5p3-flash (or nemotron no-reasoning) -> first-token logprob -> below threshold? -> glm-5p3 / flash; annotated with escalation rate, accuracy and $/1k at the -0.1 threshold. Side panel: where 82% of the cost goes (catalog tokens) and the fine-tune that removes it.
4. **Business value:** the BUSINESS.md monthly table (frontier vs chosen vs routed vs fine-tune estimate), the one-sentence claim, and the honest caveat: synthetic data, accuracy headroom is 1.7 points, cost headroom is 10x.
