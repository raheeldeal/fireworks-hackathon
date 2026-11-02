# PITCH (3 minutes) — code fix on Fireworks

Real numbers from RESULTS.md (clean table). If this task were chosen, this is the script; the headroom verdict says
it should not be, so this doubles as the "what a saturated task looks like" example.

**1. Problem and who pays (20 s).** "Every red CI run interrupts an engineer for about 20 minutes. Teams want a bot
that proposes the fix, but a bot that is wrong one time in five creates more review than it saves. The metric that
matters: does the fix pass the tests the developer did not show the model?"

**2. Task and eval (20 s).** "Execution-scored eval: 164 human-written bugs from HumanEvalFix. The model sees the
function and the one failing assert; we run the 5-10 hidden asserts in a network-less sandbox. Pass or fail, no judge
model. Three seeds for variance, ±0.6 points."

**3. Baseline (20 s).** "Off the shelf, the spread is huge: nemotron 79%, gpt-oss-120b 80%, deepseek-flash 96%,
glm-5p3-flash 99.4% at $0.26 per thousand requests. The frontier open model kimi-k3: 99.0% at $3.71, fourteen times
the price, for a worse number."

**4. What we changed (40 s, one diagram).** "We tried the three cheap levers. A rubric prompt built from the misses:
no gain. Five worked examples from a disjoint dataset: no gain. JSON mode: a loss until the parser unwrapped the fence
the model put inside the JSON. The one thing that worked is a router that costs zero tokens: after the small model
answers, we re-run the single visible assert; if it still fails or the output is malformed, we escalate to glm-5p3.
It escalated 5 of 164 requests and the large model fixed all 5."

**5. Result (40 s, the table).** "glm-5p3-flash plain: 99.4% ± 0.6 at $0.26 per thousand, 2.1 s median. Routed:
100% at $0.37. Frontier: 99.0% at $3.71. The small model is not 'close to' the frontier here, it is level with it,
at one fourteenth of the cost."

**6. Business value (20 s).** "At 60k fixes a month: $16 of inference instead of $223, and 360 wrong fixes instead
of 600. The honest version: both are rounding errors next to the 2.4 million dollars of engineer time the bot saves,
which is why pass rate, not price, picks the model."

**7. How far we pushed it (20 s, the curve).** "frontier.png: six models, fifteen configurations. The curve is flat
at the top: once a model clears 96%, nothing we did moved it. That flatness is the finding. The remaining misses are
the three problems where the one visible assert admits two different fixes; no prompt fixes an ambiguous spec, more
tests do."

## Slides
1. **Title:** "Fix the test, not the symptom: small open models for CI auto-repair." Sub: 164 real bugs, hidden-test
   scored, 6 models, 15 configurations, $1.96 of inference.
2. **Table:** the RESULTS.md clean table, rows: nemotron, gpt-oss, deepseek, glm-5p3, kimi-k3, glm-5p3-flash (3 seeds),
   verify-router. Columns: accuracy ± range, invalid, p50, $/1k.
3. **Diagram:** request → glm-5p3-flash → run the visible assert in sandbox → pass? return : escalate to glm-5p3 →
   hidden tests score. Annotate: "5/164 escalated, 5/5 fixed, +$0.11 per 1k".
4. **Business value:** 60k calls/month: $16 vs $223 inference; 360 vs 600 wrong fixes; the one-sentence claim; and the
   caveat line "pass rate picks the model, price is noise at this volume".
