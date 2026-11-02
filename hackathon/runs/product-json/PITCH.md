# Pitch: "Strict JSON from messy listings, small model beats frontier at 14x lower cost" (3 minutes)

**1. Problem and who pays (20 s).** Marketplaces and price-comparison engines ingest millions of seller-written listings: all caps, emojis, "was $68 now $54", "also available in red", "pack of 6". Search filters, ads and pricing run on eight attributes pulled from that mess. Every wrong attribute is a lost filter match or a mispriced SKU; every malformed record is a human exception. At 500k listings a day that is real money.

**2. Task and eval (20 s).** Input: one listing. Output: one JSON object, eight fields, fixed schema with enums. We locked a 200-listing test set (hash 55fec063…) where the gold attributes were sampled first and the text written around them, then regex-verified, so the labels are not a model's opinion. Score: JSON must validate against the schema, then every field must match exactly after normalisation. Headline number = all eight fields right.

**3. Baseline (20 s).** Plain prompt, six Fireworks models: small glm-5p3-flash 76.5%, the frontier kimi-k3 69%. Everyone fails the same way: they call a 6-pack a bundle and pick the crossed-out price. The frontier costs 27x more and is 2x slower and still loses.

**4. What we changed (40 s).** One slide, one diagram. A rubric prompt that defines the five traps (sale beats list price, "also available in" is not the colour sold, multipack ≠ bundle, size range ≠ size sold, accessories don't count as quantity) → 93%. Five worked examples from the training split → 95.5%, stable across three runs (95.0–96.0%). JSON-schema mode → zero invalid outputs. We also tried routing: send risky listings to the frontier. It added nothing, because after the rubric the small model is already better than the frontier.

**5. Result (40 s).** The table. glm-5p3-flash rubric + 5-shot: 95.5% all-fields, 1.4 s p50, $0.35 per 1k. kimi-k3 with the same rubric: 92.0%, 3.0 s, $5.09 per 1k. Same 100 rows head-to-head: 94–95% vs 92%. Small model wins on accuracy, latency and cost at once.

**6. Business value (20 s).** 500k listings a day: $5.3k a month vs $76k for the frontier, 525,000 fewer wrong listings a month, half the latency. Prompt caching on the 1,000-token prefix would roughly halve our cost again.

**7. How far we pushed it (20 s).** The curve: plain → rubric (+16.5) → few-shot (+2.5) → JSON mode (0 invalid) → routing (flat). What's left is 4.5%, and half of that is label ambiguity (is a sheet set a bundle?). Next: the free Muse Glimmer LoRA on 223 examples to see if a tuned model closes the last 2–3 points with no prompt at all.

## Slides
1. **Title:** "Strict JSON from messy listings: 95.5% at $0.35/1k, beating the frontier." Subtitle: 200-listing locked eval, 6 Fireworks models, 22 configurations.
2. **Table:** config | model | all-fields acc | invalid | p50 | $/1k, rows: plain small, plain frontier, rubric small, rubric frontier, few-shot small (bold), routing. Footer: 3-seed range for the two small configs.
3. **Diagram:** listing → [rubric + 5-shot prompt] → glm-5p3-flash (JSON-schema mode) → validator → JSON; a greyed-out "escalate to frontier" branch labelled "+0.0 points, +4x cost: removed". Side panel: the five traps and the per-field accuracy before/after (is_bundle 80% → 98%).
4. **Business value:** 500k listings/day: $5.3k vs $76k per month; 675k vs 1.2M wrong rows; 1.4 s vs 3.0 s. One sentence: "Define the traps, show five examples, and the small model does the frontier's job for 7 cents on the dollar."
