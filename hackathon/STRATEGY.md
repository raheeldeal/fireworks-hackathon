# Fireworks: Deploy. Winning strategy

## A. The brief, line by line, as judging criteria

| Brief says | What judges will check | What "really well" looks like |
|---|---|---|
| "Pick a task you care about" | Is the task specific and motivated? | One sentence, one input, one output, a named user who pays for it |
| "deploy a model that serves it in production" | Is there a live model id on Fireworks? | Fine-tuned model deployed, called live in the demo, p50 latency quoted |
| "Build an eval using your own data, synthetic data, or a public set" | Is the eval real? | 150+ held-out examples, automatic scoring, variance reported (3 runs) |
| "measure the tradeoffs: quality vs. efficiency, accuracy vs. latency, pass rate vs. cost" | Did you measure more than one axis? | Every run reports accuracy, p50/p95 latency, $ per 1k. Plotted, not just tabled |
| "Tune at least one dimension against your baseline" | Is there a baseline and a clear delta? | Baseline is the raw small model AND the frontier model; delta shown against both |
| "show the business value" | Is there a dollar or time number? | A workload assumption (N calls/day) and the monthly $ and error difference |
| "show how far you pushed it" | Is there a curve, not a point? | 5+ points: small raw, small+prompt, small SFT, small RFT, big raw, frontier |
| "Train a specialized model, build a smarter harness, route across models" | Did you use the platform's strengths? | At least two of: fine-tune (LoRA), RFT with Eval Protocol, routing, speculative decoding |
| "Best result wins" | Is the result impressive AND credible? | Small tuned model matches or beats frontier on your eval at 10x+ lower cost, with the failure cases shown honestly |

Hidden criteria (every hackathon): it runs when the judge touches it; the pitch fits in 3 minutes; the repo README reproduces the table.

## B. Evidence that fine-tuning beats frontier models

| Source | Task | Result | Caveat |
|---|---|---|---|
| Predibase LoRA Land (2024) | 25 tasks, Mistral-7B LoRAs | 25 of 27 adapters match or beat GPT-4; +4 to +15 points on language tasks; ~$8 per fine-tune | Against GPT-4 era models |
| Fireworks / Vercel v0 (2025) | Code fixing | 93% error-free vs. closed models, "+33%", 40x faster | Vendor-reported |
| Fireworks / Genspark (2025) | Deep research agent | +10% quality vs. SOTA closed model, ~50% cost cut, under a month | Vendor-reported |
| NVIDIA FAQ / AgileRL (2026) | Support intent classification | 99.2% tuned Nemotron vs. 90.3% Claude | Promotional page |
| Trajectory.ai (2026) | Legal agent benchmark | Smallest Nemotron 3.5 tuned in hours: 8.3% all-pass vs. Claude Opus 4.6 at 6.6% | Low absolute scores |
| Think2SQL (2026) | Text-to-SQL on BIRD | 7B with reasoning-trace SFT beats 70B open and GPT-4o | vs. GPT-4o, not GPT-5 |
| arXiv 2512.12677 (2025) | Text classification | LoRA Llama-3.2-3B beats Claude Opus 4.6 few-shot by ~3.5 points | One setup |
| Text-to-Cypher (2026) | Graph queries | Tuned small model 76.2 vs. Claude 78.6 and GPT-5 78.5 | Near parity, not a win |

Pattern: wins come on narrow, repetitive, checkable tasks (classification, structured output, code fixing, SQL). Losses or ties come on open-ended reasoning. There is no neutral leaderboard that tracks this; the closest is LoRA Land's table. Pick a task on the winning side of that pattern.

## C. Ten task and dataset options

Scored 1 to 5 on: Headroom (frontier model likely fails enough to show a gain), Scorable (automatic, unambiguous), Fireworks fit (RFT-able, deployable, speed story), Story (business value a judge gets instantly), Risk (data or scoring could eat hours; lower is better).

| # | Task | Data | Scoring | Headroom | Scorable | FW fit | Story | Risk |
|---|---|---|---|---|---|---|---|---|
| 1 | Text-to-SQL for one schema | Spider or BIRD-mini (public) | Execute both queries, compare result sets | 4 | 5 | 5 | 4 | 3 (need SQLite setup) |
| 2 | Function / tool calling for a fixed API set | BFCL v3, xLAM (public) | Exact match on tool name + args | 4 | 5 | 5 | 5 | 2 |
| 3 | Code fix: broken function + error → fixed function | HumanEvalFix / synthetic from HumanEval | Run hidden unit tests | 4 | 5 | 5 | 5 (mirrors Vercel) | 3 (sandboxing) |
| 4 | Meeting transcript → action items JSON | Synthetic from AMI/ICSI transcripts + LLM labels | Field-level F1 against gold JSON | 3 | 4 | 4 | 5 (Granola-style) | 3 (synthetic labels) |
| 5 | Legal clause classification | LEDGAR (public, 100 classes) | Accuracy / macro-F1 | 4 | 5 | 5 | 4 | 1 |
| 6 | Medical note → ICD-10 codes | Synthetic notes (no PHI) + public ICD list | Set-level F1 on codes | 5 | 4 | 5 | 5 | 4 (synthetic quality) |
| 7 | Natural language → regex | NL-RX / KB13 (public) | Does regex match the held-out positive/negative strings | 5 | 5 | 5 | 3 | 1 |
| 8 | Product page text → strict JSON schema | Amazon/ESCI product data (public) | Schema validity + field exact match | 3 | 5 | 4 | 4 | 2 |
| 9 | Support ticket → intent + priority + routing (multi-field) | Banking77 / CLINC150 (public) | Per-field accuracy; 77 to 150 classes makes it hard | 4 | 5 | 5 | 4 | 1 |
| 10 | Pick-the-right-tool among 100 MCP tools from a user request | Synthetic from real MCP tool catalogs | Exact tool match, top-1 and top-3 | 4 | 5 | 5 | 4 | 2 |

Bonus ideas if you want stranger: address parsing to components (libpostal data; small models fail), unit-test generation scored by mutation kill rate, SQL error repair, email → calendar event JSON, review → aspect sentiment JSON (SemEval ABSA).

My ranking for winning: 2, 1, 3, 9, 7. Reasons: 2 is Fireworks' home turf and NVIDIA/Microsoft judges care about agents; 1 has the best paper trail; 3 is the Vercel story; 9 is lowest risk and still hard (150 classes); 7 is the surprise entry where frontier models genuinely stumble and scoring is bulletproof.

## D. Workstreams

| | Workstream | Deliverables | Who tomorrow |
|---|---|---|---|
| A | Task and eval design | One-line task, input/output spec, scoring function, train/test split, variance plan | You |
| B | Data pipeline | Download, clean, convert to JSONL, synthetic augmentation if needed, leakage check | Engineer 1 |
| C | Baselines and model sweep | Small/medium/large/frontier on the test set; accuracy, p50/p95, $/1k | Engineer 2 (kit does this) |
| D | Harness interventions | Prompt rubric, few-shot, structured output mode, routing small→big, guardrails | Engineer 2 |
| E | Fine-tuning | SFT data format, SFT job, RFT scorer, RFT job, monitoring | Engineer 1 |
| F | Deployment | Deploy LoRA, model id, latency test, speculative decoding on/off | Engineer 1 |
| G | Analysis | Frontier chart, error analysis of misses, variance across 3 runs | You + kit |
| H | Business value model | Workload assumption, $/month per option, errors/month per option | You |
| I | Demo and pitch | 4 slides, live curl, 3-minute script, rehearsed twice | You |
| J | Submission and repo | README with table, reproducible scripts, form filled by 4:00 | You |
| K | Team ops | Roles, hourly standup, scope cuts, mentor conversations | You |

## E. What runs overnight

For each of the 5 tasks you pick: B, C, D (prompt + routing), G (chart), H (draft) fully. E and F on the top 2 by headroom (SFT job on each, RFT attempt on one). I and J as skeletons with real numbers filled in. Output: `MORNING.md` ranking the 5 by evidence, with charts, and the pitch for the top one drafted.

Budget: ~2,500 inference calls across 5 tasks and 5 models (~$3), two SFT jobs (~$2 to $5), RFT free under 16B. Cap: $10. Stops if the cap is hit.
