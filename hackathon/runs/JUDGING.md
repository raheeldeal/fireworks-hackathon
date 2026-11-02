# Judging log

Rubric (1 to 5 each, from STRATEGY.md section A): task clarity, eval rigor, tradeoff measurement, baseline and delta, business value, frontier curve, platform use, headroom (does the frontier struggle), reproducibility. Every reported accuracy is recomputed from per-row files with `common/verify.py` before scoring.

## Run 8: banking intent routing (Banking77, 77 classes)
Verified: 154-row test set, sha256 3547e8f9bc1491ce; ledger $1.99 over 3,492 calls; all 23 reported accuracies reproduce exactly from raw rows.

| Criterion | Score | Note |
|---|---|---|
| Task clarity | 5 | One input, one of 77 labels, real public data |
| Eval rigor | 5 | Held-out official split, 4 row orders for variance (±2.6), misses analyzed |
| Tradeoffs | 5 | Accuracy, p50/p95, $/1k for 23 configs; thinking on/off measured |
| Baseline and delta | 4 | Clear, but deltas mostly inside noise |
| Business value | 4 | Routing: frontier accuracy at 1/3 cost; needs the workload $ |
| Frontier curve | 5 | 23 points plus a 7-threshold routing curve |
| Platform use | 4 | Reasoning-effort control, JSON schema, routing; SFT pending |
| Headroom | 2 | Frontier 88%, small 85 to 87%; label noise caps everything |
| Reproducibility | 5 | Scripts, ledger, locked set |

**Total 39/45. Verdict:** excellent execution, wrong task for winning. The run's own conclusion is right: this is a control that shows where headroom is *not*. Keep its routing demo and calibration finding (GLM's self-reported confidence is usable, Nemotron's is not) as reusable material for whichever task wins.

Reusable gotchas from this run: prompt engineering (rubric, few-shot, JSON schema) *lowered* accuracy on glm-5p3-flash by 1 to 4 points; turning thinking off cost 4 points on GLM but nothing on Nemotron while making it 7x faster; kimi-k3 at $5.60 per 1k is 22x the small model.

## Run 10: meeting transcript to action items (synthetic, gold-first)
Verified: 150-row test set, sha256 6143b59c7fc675b7; ledger $2.70 over 2,885 calls; micro-F1 recomputed from per-row tp/n_pred/n_gold matches reported F1 to 4 decimals for all key configs (my generic verifier flagged mismatches only because it assumed exact-row accuracy; the run reports F1, correctly). kimi-k3 scored on 70 rows only (cap).

| Criterion | Score | Note |
|---|---|---|
| Task clarity | 5 | Granola-style, clear JSON output |
| Eval rigor | 4 | Gold-first synthetic, leak-checked, noise audit done; label noise ~2 to 3 F1 points from the writer adding commitments |
| Tradeoffs | 5 | F1, P/R, due accuracy, latency, $/1k across 6 models and 5 prompts |
| Baseline and delta | 3 | Small beats frontier, but every model is 0.92 to 0.97: saturated |
| Business value | 4 | "$7.4k/month frontier premium buys nothing" is a real but flat story |
| Frontier curve | 4 | Drawn, but flat |
| Platform use | 3 | No fine-tune (SDK install denied); routing and JSON mode tried |
| Headroom | 1 | None; the run says so itself and proposes a harder variant |
| Reproducibility | 5 | Scripts, ledger, noise audit |

**Total 34/45. Verdict:** not a winning task as built; saturated at the frontier. Reusable: the gold-first synthetic data recipe worked and is leak-proof; precision (0.89 to 0.95) is the only axis with room, so a distractor-heavy variant could become a real task.

## Run 2: text-to-SQL (Spider dev, execution accuracy) — PROVISIONAL, SFT pending
Verified: 180-row test set, sha256 4efe94e1f88833af; all reported accuracies reproduce from per-row files. RESULTS.md prose is stale (written during the outage); numbers below are from the raw results.

Key numbers (3 seeds where shown): glm-5p3-flash plain 85.6 to 86.7%; kimi-k3 (frontier, 100 rows) 77 to 79%; glm-5p3 (large) 73.9 to 76.1%; gpt-oss-120b 77.2%; Muse Glimmer 30B base 74.4%; nemotron 67 to 71%. Rubric and few-shot prompts *hurt* glm-flash (80.6, 82.2). Routing glm-flash → glm-5p3 never beats glm-flash alone.

Provisional read: the frontier does not beat the small model here; the small model beats the frontier by ~8 points. That is a different story from "headroom" but a stronger one for judges: "the cheapest model on the platform beats the frontier on SQL, and fine-tuning pushes it further." Final score waits on the Muse Glimmer SFT (base 74.4%; if the LoRA lands near or above 86% that completes the curve).

## Run 5: legal clause classification (LEDGAR, 100 classes) — SFT pending
Verified: 199-row test set, sha256 08f0ae5dc704e13b; ledger $2.32 over 3,498 calls; all accuracies reproduce.
Key numbers: best small glm-5p3-flash JSON mode 68.8% ± 0.5 (3 seeds) at $0.36/1k; kimi-k3 73.8% on 80 rows at $7.24/1k (on the same 80 rows glm-flash scores 76.2%); every model 57 to 74%; prompting adds ≤2 points; routing cannot beat the best small model. Published fine-tuned encoders reach ~88% on LEDGAR, so there is 15 to 20 points of real headroom that only training can reach.

| Criterion | Score | Note |
|---|---|---|
| Task clarity | 5 | Public data, 100 labels, clear buyer (CLM vendors) |
| Eval rigor | 5 | Stratified held-out, 3 seeds, rubric derived from train-only dev run |
| Tradeoffs | 5 | Full table, think on/off |
| Baseline and delta | 4 | Clear; frontier gap small, headroom real |
| Business value | 4 | 20x cheaper at equal accuracy |
| Frontier curve | 4 | Drawn; SFT point missing |
| Platform use | 3 | SFT queued on the shared slot |
| Headroom | 5 | Frontier stuck at ~74%, ceiling ~88% known from literature |
| Reproducibility | 5 | |

**Total 40/45 provisional. Verdict:** the clearest candidate for "small fine-tuned model beats frontier." Everything hinges on the SFT row: ≥80% makes this the headline task; <75% makes it a label-noise story.

## Run 7: product text to strict JSON (synthetic gold-first) — SFT pending
Verified: 200-row test set, sha256 55fec063858774d3; ledger $2.61 over 3,163 calls; all accuracies reproduce.
Key numbers: plain prompt every model 68 to 79% including the frontier; rubric + 5-shot lifts glm-5p3-flash to 95.5% (3 seeds 95.0 to 96.0) at $0.35/1k vs kimi-k3 92.0% with the same rubric at $5.09/1k. Routing adds nothing. Headroom was in the prompt, not the model.

| Criterion | Score | Note |
|---|---|---|
| Task clarity | 5 | |
| Eval rigor | 4 | Synthetic gold; ~half of remaining misses are label ambiguity |
| Tradeoffs | 5 | |
| Baseline and delta | 4 | +16.5 points from the rubric is a huge, honest delta |
| Business value | 4 | 14x cheaper, small beats frontier |
| Frontier curve | 4 | |
| Platform use | 3 | JSON mode used; SFT pending |
| Headroom | 3 | Real with a plain prompt, mostly gone after the rubric |
| Reproducibility | 5 | |

**Total 37/45 provisional. Verdict:** the safe fallback. A credible "small beats frontier at 14x lower cost" story with airtight scoring, but the win is from prompting, which judges may discount.

## Run 9: pick the right tool from 100 (synthetic gold-first)
Verified: 180-row test set, sha256 bb50067286893483; ledger $2.53 over 5,078 calls; all accuracies reproduce. SFT skipped: dataset uploads return HTTP 403 on this account (relevant for tomorrow: check that upload permission exists before planning SFT).
Key numbers: glm-5p3-flash plain 98.3% ± 0.6 at $0.28/1k vs kimi-k3 95.0% (100 rows) at $6.15/1k; saturated on accuracy. The real finding is cost: 82% of every call is the 100-tool catalog, so a fine-tune that bakes the catalog in would cut cost ~10x.

| Criterion | Score | Note |
|---|---|---|
| Task clarity | 5 | |
| Eval rigor | 5 | 3 seeds, 180 rows, keyword-retrieval harness variant measured |
| Tradeoffs | 5 | Cost decomposition (catalog vs. answer) is a standout |
| Baseline and delta | 3 | Accuracy saturated |
| Business value | 4 | "10x cheaper routing" is pitchable if the fine-tune happens |
| Frontier curve | 4 | |
| Platform use | 2 | No SFT (403 on uploads) |
| Headroom | 2 | 1.7 points on accuracy; large on cost only |
| Reproducibility | 5 | |

**Total 35/45. Verdict:** saturated on accuracy; interesting only if re-framed as a cost story with a catalog-free fine-tune, which this account could not run tonight.

## Run 1: function calling (BFCL v4 simple+multiple)
Verified: 200-row test set, sha256 a9ef43af57e1e883; ledger $2.47; all accuracies reproduce.
Key: nemotron (reasoning off, tool_choice required) 91.0% ± 0.5 strict at $0.054/1k, p50 0.40 s; kimi-k3 88.0% at $3.16/1k, p50 1.85 s; glm-5p3 90.0%. Ceiling ~95% (9 rows nobody gets, BFCL conventions). The naive 14-point gap was max_tokens truncation of hidden reasoning. Free LoRA run and scored.
Scores: clarity 5, rigor 5, tradeoffs 5, delta 4, business 5, curve 5, platform 5, headroom 2, repro 5. **Total 41/45.** Verdict: no accuracy gap to close, but the strongest cost/latency story of the ten (58x, 4.6x) on a public benchmark with the co-host's model. Recommended headline task, pitched as cost and latency, not "closing a gap".

## Run 3: natural language to regex (KB13 / NL-RX)
Verified: 200-row test set, sha256 ef955dce4c2c19c5; ledger $1.09; all accuracies reproduce.
Key: off the shelf every model 60 to 74%; a 10-rule prompt lifts glm-flash to 95.0% (4 seeds identical) at $0.124/1k vs kimi-k3 96.0% at $2.64/1k. Free LoRA on 30B base: 30.5% → 93.5% with the plain prompt, i.e. the fine-tune learned the conventions instead of being told them.
Scores: clarity 5, rigor 5, tradeoffs 5, delta 4, business 3, curve 5, platform 5, headroom 2, repro 5. **Total 39/45.** Verdict: saturated at the frontier, but the prompt-vs-finetune comparison (+27 from rules, +63 from LoRA) is the cleanest demonstration of "how far you pushed it" of the night. Reusable as a slide regardless of task.

## Run 4: code fix (HumanEvalFix)
Verified: 164-row test set, sha256 2bc0883f6eecfbed; ledger $1.96; all accuracies reproduce.
Key: glm-flash 99.4% (3 seeds) vs kimi-k3 99.0%; same two misses for every strong model. SFT skipped.
Scores: clarity 5, rigor 5, tradeoffs 4, delta 2, business 3, curve 3, platform 2, headroom 1, repro 5. **Total 30/45.** Verdict: saturated; drop.

## Run 5 (final): legal clauses
SFT landed: Muse Glimmer 30B LoRA on 500 clauses scores 68.8%, exactly tying glm-flash JSON mode, sharing 44 of 62 misses (near-synonym headings). Headroom revised 5 → 2; platform 3 → 5. **Total 38/45.** Verdict: honest negative result; the ceiling is label convention, not model size. Drop as headline; keep as the "we tried, here is why it didn't move" slide if asked about fine-tuning limits.
