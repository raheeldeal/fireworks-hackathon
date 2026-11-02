# 3-minute pitch: "Action items that actually happened"

Numbers are from RESULTS.md (150 locked test transcripts, item F1, serverless list prices).

1. **Problem and who pays (20s).** Every meeting-notes product (Granola, Otter, Zoom AI Companion) promises action items. Users judge it by the one task it missed or the one it invented. At 50k meetings a day, each F1 point is about 54k wrong action items a month. The obvious answer is "use the biggest model". We tested that.

2. **Task and eval (20s).** Transcript in, JSON list of {owner, task, due} out. We built 400 synthetic meetings gold-first: we sampled the commitments and the distractors (parked ideas, rejected suggestions, finished work, "if there's time" offers) before asking a model to write the dialogue, so the labels are exact by construction. 150 are locked as the test set (sha256 6143b59c…). Scoring: owner match plus fuzzy task match, item-level F1, exact due-date accuracy. Zero invalid outputs across every model.

3. **Baseline (20s).** Plain prompt. Smallest model (nemotron 30B-A3B, $0.06/1k): F1 0.921. glm-5p3-flash ($0.17/1k): 0.938. Frontier kimi-k3 ($5.33/1k, 2.9 s): 0.953. The large glm-5p3 at $1.56/1k: 0.930, worse than its own flash variant.

4. **What we changed (40s).** Four harness moves on the small model, each measured: (a) a 10-rule rubric prompt: F1 fell to 0.920, the rules made it drop real items; (b) JSON mode: plain json_object collapsed the list to one object (148/148 invalid), a schema-constrained wrapper fixed it at 0.929; (c) five worked examples from the train split: 0.962 ± 0.001 over 3 runs; (d) routing on self-reported confidence: items under 0.9 confidence were wrong 96% of the time, so escalating those rows to deepseek lifted F1 to 0.946 at thr 0.9, 0.957 at thr 0.95, but deepseek alone (0.965 at $0.37/1k) beats every routing point.

5. **Result (40s).** The table. Best small config: glm-5p3-flash + 5-shot, F1 0.961, 1.1 s p50, $0.74/1k. Frontier: 0.953, 2.9 s, $5.33/1k. Best overall: deepseek-v4p1-flash plain, 0.965, 1.3 s, $0.37/1k. Variance on the small baseline across 4 runs: ±0.002.

6. **Business value (20s).** At 50k meetings/day: frontier $8.0k/month; deepseek $552/month; 5-shot small $1.1k/month (about $350 with prompt caching). Switching from frontier to deepseek saves $7.4k/month and removes about 62k wrong items a month. Not "cheaper and almost as good": cheaper and better.

7. **How far we pushed it (20s).** frontier.png: 18 configurations. The honest finding is that this task is near its ceiling for every model: about 2 to 3 points of the remaining error are label noise in the synthetic data and paraphrases our 0.6 matcher rejects. The win is not "small beats frontier by a mile"; it is "the frontier premium buys nothing on this task, and a $0.15 model with five examples is where production should run".

## Slides
1. **Title:** "Action items that actually happened" — transcript -> {owner, task, due}; who pays: meeting-notes products, 50k meetings/day.
2. **Table:** config × F1 × $/1k × p50 for nemotron, glm-5p3-flash plain / 5-shot, deepseek, glm-5p3, kimi-k3, routing thr 0.9.
3. **Diagram:** transcript -> glm-5p3-flash (+5 examples) -> per-item confidence -> drop <0.85 / escalate row <0.9 to deepseek; with the measured escalation rate (15%) and the finding that items under 0.9 confidence were wrong 96% of the time.
4. **Business value:** $/month and wrong items/month for frontier vs deepseek vs 5-shot small; the one-sentence claim.
