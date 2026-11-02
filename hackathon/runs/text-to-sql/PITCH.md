# Pitch (3 minutes): "The small model is the accurate one"

**1. Problem and who pays (20 s).** Every analytics vendor is shipping "ask your data in English". The product fails quietly: a query that runs and returns the wrong number. At 50,000 questions a day, every accuracy point is 15,000 wrong answers a month, each costing an analyst ~10 minutes to catch and redo. Accuracy is the business metric; inference cost is a rounding error next to it.

**2. Task and eval (20 s).** Text-to-SQL on Spider: natural-language question + schema in, one SQLite query out. We locked a 180-question test set across all 20 Spider dev databases and score by *executing* both the gold and the predicted SQL on the real database and comparing result sets. No human judgment, no LLM judge, deterministic, re-runnable in two minutes.

**3. Baseline (20 s).** Six open models on Fireworks with the same plain prompt. The frontier open model, kimi-k3, gets 78% at $2.80 per 1k questions and 2.3 s median latency. The 30B NVIDIA model with thinking on: 67%, with a third of its answers invalid because it talks itself out of token budget.

**4. What we changed (40 s).** Three levers, all measured on the same 180 questions:
- *Harness.* Turning thinking off on nemotron-30b-a3b: 67% → 69% and 7× cheaper, 8× faster (0.28 s). A rubric prompt of rules learned from the misses: +1 to +2 points on nemotron, but it *hurt* glm-5p3-flash (86% → 81%): the small model already knows SQL; more instructions only add ways to deviate from Spider's conventions.
- *Routing.* Small model answers; escalate when its SQL fails to execute or returns nothing. Measured at four confidence thresholds. Finding: routing to the "bigger" model never beats the small model alone here, because the bigger models are *worse* on this task. Routing only helps when the fallback is actually better, and here it isn't.
- *Fine-tuning.* LoRA SFT of Muse Glimmer 30B on 450 Spider training questions (free on Fireworks serverless training this month), scored on the same test set through the serverless sampler. Base vs tuned: see RESULTS.md.

**5. Result (40 s).** [table slide] glm-5p3-flash, plain prompt: **85.4% ± 1.7 across four runs**, $0.10 per 1k, 1.1 s median. That is **+8 points over kimi-k3 at 1/28th the cost**, and +10 over glm-5p3 (its own big sibling, 75.0% ± 1.1) at 1/4 the cost. Where kimi fails, it over-engineers: LEFT JOINs that add zero-count rows, CASTs on text columns, extra DISTINCTs. Where the small model fails, 1 in 3 misses is a column-order or projection quirk of the benchmark (lenient score 87.9%).

**6. Business value (20 s).** At 1.5M questions a month: glm-5p3-flash costs $155/month versus $4,170 for kimi-k3, and returns ~115,000 fewer wrong answers, about 19,000 analyst hours. The decision isn't "small to save money"; it is "small because it is better, and it happens to be 28× cheaper".

**7. How far we pushed it (20 s).** [curve slide] Fourteen configurations on one accuracy-vs-cost chart. The frontier of the chart is the small model; the frontier *model* sits bottom-right. Run-to-run variance at temperature 0 is ±2 points, so we report four runs, not one. The headroom left is in the benchmark's own conventions, which is exactly what fine-tuning on in-distribution data targets.

## Slides
1. **Title:** "Text-to-SQL on Fireworks: the small model is the accurate one". Subtitle: 180 questions, 20 schemas, execution-scored, 14 configs, 4 runs for variance.
2. **Table:** the results table from RESULTS.md (accuracy, invalid, p50/p95, $/1k, seeds) with glm-5p3-flash and kimi-k3 rows highlighted.
3. **Diagram:** the pipeline: question + schema → model → SQL → *execute on SQLite* → compare result sets → score; a side box for the routing gate (execute → invalid/empty? → escalate) and the SFT loop (450 Spider train rows → LoRA on serverless trainer → sampler checkpoint → same scorer).
4. **Business value:** the BUSINESS.md table, with the line "every accuracy point = 15,000 wrong answers/month = 2,500 analyst hours".
