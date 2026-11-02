# Harness, tracing, training and dashboard: plan

Status: **plan, not yet implemented.** Written 2026-11-02. Items marked *(verify)* are assumptions to check before relying on them.

## 1. The story (what we sell)

**One line:** a self-improving text-to-Cypher system. The harness makes a cheap open model accurate. Its own traces then teach it to get the answer right the first time, which makes it cheaper and faster too.

Three acts, each backed by one chart:
1. **"Frontier models still miss."** claude-sonnet-4.6 scores 56.6% on this dataset (published). Analysts can't trust a query they can't check.
2. **"Check the work."** A harness (examples, quick fixes, run-and-repair, escalation) takes a cheap open model past the frontier score. Every step is shown in a Langfuse trace: wrong query, database error, repair, correct rows.
3. **"Learn from the work."** Fine-tuning on the harness's own successful traces moves the model up and to the left on the Pareto chart: more accurate, fewer repair calls, lower cost and latency.

How it maps to the judging weights in PLAN.md:

| Weight | What covers it |
|---|---|
| Benchmark 40% | Locked hashed test set; paired CIs; tier and graph breakdowns; published frontier reference |
| Business 25% | Cost per correct answer and latency on the Pareto chart; analyst workload maths |
| Technical 20% | Ablation ladder (harness components, then six fine-tuning recipes: SFT, self-improving loop, DPO, RL); trace-to-training loop |
| Demo 10% | Live question → Langfuse trace showing the repair → correct rows; Pareto chart |
| Docs 5% | README reproduces every number |

## 2. Goal and win condition (fixed before any run)

- **Accuracy:** open model + harness ≥ **56.6%**, the published zero-shot score of claude-sonnet-4.6. The 95% CI on our 200 rows must exclude anything below it.
  - **Stretch:** ≥ **62.5%**, the published claude-sonnet-4.6 + CypherGuard score.
- **Pareto:** at least one of our configs is on the frontier for accuracy vs cost per question, and for accuracy vs p50 latency.
  - **Self-improvement:** fine-tuning on traces beats the same harness without it on cost or latency, without losing accuracy.

The frontier numbers come from the CypherGuard paper (arxiv.org/html/2610.41755), measured on a 1,003-question audited subset of the same Neo4j Text2Cypher 2024 dataset. Our test set is a different 200-row subset of that dataset. We report it as a reference, not a head-to-head, and we do not run the frontier model ourselves.

## 3. What already exists (verified)

| File | What it does |
|---|---|
| `executor.py` | `execute(graph, cypher)` runs a read-only query on the public Neo4j demo server. Returns rows or an error. |
| `score.py` | `score(gold, pred, gold_cypher)` returns `correct` / `wrong` / `error` / `empty`. `clean_pred(text)` pulls the Cypher out of model output. |
| `test_score.py` | 12 tests, all passing. |
| `data/test.jsonl` | 200 locked rows: 5 graphs × 40, hash in `TEST_HASH`. Every gold query returns 1–200 rows. |
| `data/train.jsonl` | 500 rows, leak-checked against test. |
| `raw/` | Full dataset download. The 5 graphs have 8,379 train rows (gitignored). |
| `../submission/fw.py` | Fireworks client with retries, cost ledger and spend cap. To be adapted. |
| `../submission/train/tune.py` | Working LoRA SFT and rejection sampling on Muse Glimmer 30B through the Fireworks Serverless Training API. To be adapted. |

## 4. Prerequisites

- [x] `FIREWORKS_API_KEY` in `hackathon/cypher/.env`. Serverless inference returns HTTP 200 and lists 29 models (2026-11-02).
- [x] Langfuse project on us.cloud.langfuse.com. Keys are in `hackathon/cypher/.env` (git-ignored); the auth check passed 2026-11-02.
- [x] Python 3.11 venv at repo root `.venv`: `neo4j`, `datasets`, `pytest`, `langfuse` 5.1.0, `fireworks-ai[training]` 1.2.30, `transformers` 5.22.1.
  - Langfuse 5.1.0 is newer than the v4 docs, so its API is checked against the installed package before use.
- [x] Serverless training sampler works on this account: one test sample from Muse Glimmer 30B base, 2026-11-02.
  - The base model opens a `to=self` reasoning channel unless the reply is pre-filled with ` to=user<|message|>`, as `../submission/train/tune.py` already does.
- [ ] Creating a training session (needed for FT1) is not tested yet; it is checked at the start of M5.
- **Model availability**, checked with this key on 2026-11-02:

  | Model | Serverless inference | Used for |
  |---|---|---|
  | Muse Glimmer 30B | **no**, training sampler only ($1.96/M in, $4.88/M out) | R1–R11 |
  | Qwen 3.6 35B A3B | **no**, training sampler only ($0.45/M in, $1.335/M out) | R12 |
  | kimi-k3 | yes | escalation (R5) and harvest |

## 5. The harness

The model never changes; the harness only controls what the model sees, checks its work, and decides when to ask for help. Each stage is a flag, so every ablation row is the same command with different flags.

```
question ──► [1 examples] ──► model writes Cypher ──► execute ──► ok, has rows? ──► answer
                                                         │ no
                                                         ▼
                                           [2 arrow fix]  (no model call)
                                                         │ still no
                                                         ▼
                                           [3 repair]  error/empty + hints ──► model, up to N times
                                                         │ still no
                                                         ▼
                                           [4 escalate]  same loop on a bigger model
```

| # | Stage | Flag | What it does | Model calls |
|---|---|---|---|---|
| 1 | Examples | `--shots K` | Add the K most similar train questions from the same graph to the prompt. Ranking is keyword overlap, deterministic. | 0 |
| 2 | Arrow fix | `--fix` | On an empty result, reverse relationship arrows the schema declares only the other way, and keep the change only if rows come back. | 0 |
| 3 | Repair | `--repair N` | Send back the raw Neo4j error, or "no rows". Add schema hints (labels, relationship types or properties not in the schema) and value hints (similar stored values for string literals). Up to N retries; stop if the query repeats. | 0–N |
| 4 | Escalate | `--escalate MODEL` | If stages 1–3 still end in an error or empty result, run the same loop on a bigger model. | 0–(1+N) |

**Honesty rule:** the harness never sees gold. It decides only from errors, empty results and the schema. Gold is used afterwards, by `score.py`, to grade the final answer.

**Known caveat:** the harness treats an empty result as suspicious. Every gold answer in our test set is non-empty, so this heuristic is slightly favoured on our data. Both reference papers use the same heuristic; we state it in the results.

## 6. Tracing (Langfuse)

Every question becomes one Langfuse trace:

```
trace  question q123 · graph · config tag · model
 ├─ span        retrieve      → example ids
 ├─ generation  attempt 1     → prompt, Cypher, tokens, cost, latency
 ├─ span        execute       → status, error, row count, seconds
 ├─ span        arrow fix     → changed? rows?
 ├─ generation  repair 1      → hint, Cypher, tokens, cost, latency
 ├─ span        execute
 └─ score       outcome = correct | wrong | error | empty   (added after grading)
```

Rules:
- **Local JSON is the source of truth.** Every run writes `results/<tag>.json` (§7). Langfuse is a mirror for browsing, filtering and the demo. If Langfuse keys are missing, tracing turns off and nothing breaks.
- **Test vs train traces are kept apart.** Test-run traces are tagged `split=test` and are never used for training. Training traces come only from harness runs on train questions (`split=train`).
- **Volume:** a 200-row run is about 1,200 observations, so the free tier covers roughly 25 test runs plus one harvest of about 2,000 train questions. Bigger harvests write local JSON only.
- **SDK details** (v4 `@observe`, scores, export) are read from langfuse.com docs at implementation time and pinned in requirements.

## 7. Files to write

Each kept small and commented:

| File | Responsibility |
|---|---|
| `fw.py` | Fireworks chat client: retries, ledger (`ledger.csv`), hard cap **$45**, pricing table. |
| `tracing.py` | Thin Langfuse wrapper. A no-op when keys are missing. |
| `retrieve.py` | Keyword-overlap retriever over train questions, per graph. |
| `fixes.py` | Parse the relationship list in the schema. Arrow-direction fix. Schema hints and value hints. |
| `harness.py` | `solve(row, cfg) -> trace`: runs stages 1–4 and records every attempt. |
| `run_eval.py` | CLI: one config over a question file, then `results/<tag>.json`. `--split train` is used for harvesting traces. |
| `compare.py` | Paired comparison of two result files: bootstrap 95% CI on the accuracy difference, plus a McNemar test. |
| `build_sft.py` | Turn train-split traces into training files for FT2 and FT3 (§9). Runs the leak check. |
| `dashboard/` | Static page that reads `results/*.json` (§10). |
| `test_harness.py` | Unit tests for `retrieve.py`, `fixes.py` and `build_sft.py`. No network. |

**Result file shape** (one per run):

```
{ "tag", "split", "model", "config": {...}, "created",
  "summary": { "accuracy", "ci95", "n", "by_tier", "by_graph", "by_stage",
               "cost", "cost_per_question", "cost_per_correct", "calls_per_question",
               "p50_secs", "p90_secs" },
  "rows": [ { "id", "graph", "tier", "question", "gold_cypher", "final_cypher", "outcome", "stage",
              "attempts": [ { "source", "prompt", "output", "cypher", "status", "error", "n_rows", "secs" } ],
              "calls", "in_tokens", "out_tokens", "cost", "secs", "langfuse_trace_id" } ] }
```

- `stage` says where the answer came from: `first`, `fix`, `repair1..N` or `escalate`.
- `secs` is end-to-end wall time, including database time. The demo server takes about 1 s per query, so repair steps cost latency as well as money.

## 8. Ablation matrix

All rows run on the same 200 test questions, at temperature 0.

| Row | Model | Harness | Training | Question it answers |
|---|---|---|---|---|
| R0 | claude-sonnet-4.6 (published) | n/a | n/a | The bar |
| R1 | Muse Glimmer 30B | none | none | Where does the open model start? |
| R2 | Muse Glimmer 30B | `--shots 3` | none | Do examples help? |
| R3 | Muse Glimmer 30B | `+ --fix` | none | Do free code fixes help? |
| R4 | Muse Glimmer 30B | `+ --repair 3` | none | Does run-and-repair help? |
| R5 | Muse Glimmer 30B | `+ --escalate kimi-k3` | none | How much does escalation buy, at what cost? |
| R6 | Muse Glimmer 30B + **FT1** | full | SFT on gold | Does training on the dataset's answers help? |
| R7 | Muse Glimmer 30B + **FT2** | full | SFT on traces, first-try | Do our own checked traces beat the dataset's answers? |
| R8 | Muse Glimmer 30B + **FT3** | full | FT2 + repair turns | Does learning to repair help further? |
| R9 | Muse Glimmer 30B + **FT4** | full | self-improving loop, 2 rounds | Does the model keep improving on its own outputs? |
| R10 | Muse Glimmer 30B + **FT5** | full | DPO on right-vs-wrong pairs | Does seeing its own mistakes help more than seeing only successes? |
| R11 | Muse Glimmer 30B + **FT6** | full | RL (GRPO) with execution reward | Does reward from the database beat imitation? |
| R12 | Qwen 3.6 35B A3B + best recipe | full | best of FT1–FT6 | How cheap and fast can we go? |

- R1 → R5 is the harness curve. R6 → R11 is the training curve. Every row is one point on the Pareto charts.
- **R2–R5 come from one run.** The stages run in order at temperature 0, so the R5 trace already contains what R2, R3 and R4 would have returned: R2 is the first attempt, R3 the state after the arrow fix, R4 after the last repair. Each row's accuracy, cost and latency are read by cutting the trace at that stage, counting only the calls and seconds up to that point. This is exact, not a simulation, and saves three paid runs.
- Model choices depend on the §4 checks. If Muse Glimmer base is not available at serverless rates, R1–R5 use the training sampler at $1.96/M in and $4.88/M out.
- nemotron-lightning-3p5-30b-a3b was dropped as the small model: an earlier session found it deprecated on 2026-11-07.

## 9. Training recipes

All training runs on the **Fireworks Serverless Training API** (LoRA only), adapted from `../submission/train/tune.py`. Facts checked 2026-11-02 at docs.fireworks.ai/fine-tuning/training-api/serverless:
- **Managed RFT is deprecated** and accepts no new jobs. RL now runs through the Training API, which covers SFT, DPO, ORPO, RL, distillation and custom loops.
- **Only SFT on Muse Glimmer 30B is free**, until 2026-11-30. The cookbook says RL and DPO are not covered by the offer. They are billed per training token: **Muse Glimmer 30B $5.86/M**, Qwen 3.6 35B A3B $2.14/M.
- **Sampling is paid on every model.** Muse Glimmer 30B: prefill $1.96/M (repeated prefixes cached at $0.39/M), sample $4.88/M.

| # | Recipe | Family | Training data | Teaches the model to… | Training cost |
|---|---|---|---|---|---|
| FT1 | **SFT on gold** | SFT | Train rows for the 5 graphs (up to 8,379). Gold queries are run first; only those that execute and return rows are kept. Prompt format = harness format, with 3 retrieved examples. | write queries like the dataset's answers | free |
| FT2 | **SFT on traces, first-try** (distillation) | SFT | Harvest: run the full harness (R5) on about 1,500 train questions. From every trace whose final answer matches gold, take the final query and train it as the answer to the *first* prompt. | get it right first time, so repair calls, cost and latency drop | free |
| FT3 | **FT2 + repair turns** | SFT | FT2 data, plus the repair pieces from successful traces: (first prompt → wrong query → error/hint → fixed query). | use error messages well when it slips | free |
| FT4 | **Self-improving loop** (rejection sampling, STaR-style) | SFT, iterated | Round 1 is FT2/FT3. Round 2: the best fine-tuned model runs the harness on about 1,000 *new* train questions. Keep the traces whose rows match gold, add them to the round-1 data, retrain. | improve on its own outputs, round after round | free (sampling paid) |
| FT5 | **DPO** | Preference | From traces on the same question: a query that matched gold (chosen) vs one that ran but was wrong, or errored (rejected). About 400 pairs. | prefer correct queries over its own typical mistakes | paid |
| FT6 | **RL with execution reward** (GRPO-style, cookbook `serverless_rl` example) | RL | Train questions only. Reward = 1 if rows match gold. Partial credit by row overlap, a penalty if the query errors. Starts from the best SFT checkpoint. A small run: about 30 steps × 8 questions × 4 samples. | maximise the database-checked reward directly | paid |

Why traces can beat gold:
- **Better coverage:** traces include questions where the base model's own phrasing differs from the dataset's.
- **Verified answers:** every trace answer was checked against gold rows by execution.
- **Teaches recovery:** FT3 also teaches the model to recover from errors, which gold data never shows.
- **Shared data:** one harvest feeds FT2, FT3, FT4's first round and FT5's pairs.

The harvest uses the cheap-then-escalate harness itself, so most questions cost cheap-model prices.

**Order:** FT1 → FT2 → FT3 (free training) → FT6 (RL) → FT4 → R12. FT5 (DPO) runs only if money is left. See §11 for the tiers and spending checks.

**Before FT6:** confirm the built-in RL loss names and the `serverless_rl` example in the fw-ai/cookbook repo *(verify)*.

**Leak control:**
- Harvest runs only on train questions.
- `build_sft.py` drops any row whose question or gold query appears in test, and re-runs the existing leak check.
- Test traces are never read by any training script.

**Serving:** a trained LoRA is served only on a dedicated deployment, per `../submission/train/DEPLOY.md`. We evaluate through the training sampler, about $0.70–1.50 per 200-row run (measured in tier 0), and rent a deployment only for the live demo if wanted.

## 10. Dashboard

A single static HTML page that reads `results/*.json` and is regenerated after every run. Views, in order:

1. **Pareto: accuracy vs cost per question.**
   - One dot per config (R1–R12). Frontier configs are connected; dominated ones are faded.
   - Reference: claude-sonnet-4.6's accuracy is published. Its cost is *estimated* from our token counts at its list price, and labelled as an estimate.
2. **Pareto: accuracy vs p50 latency.** Same dots. No frontier reference point, since we have no published latency.
3. **Ablation ladder:** accuracy for R1–R12 with 95% CIs, plus reference lines at 56.6% and 62.5%.
4. **Where answers come from:** per config, the share answered at each stage (first / fix / repair / escalate / still wrong). This shows FT2 and FT3 shifting answers to "first".
5. **Breakdown:** accuracy by graph and by tier.
6. **Question explorer:** gold query, every attempt with its error, and the final result, with a link to the Langfuse trace.
7. **Training and spend:** loss (and reward, for FT6) curves for FT1–FT6, plus ledger spend against $45.

## 11. Budget ($50 credits, hard cap $45 in the ledger)

Spending rules:
- **Free first:** SFT on Muse Glimmer is free, so every SFT recipe runs before anything paid.
- **Read one run many ways:** R2–R5 come from one run (§8). Temperature 0 means one run per config, not three seeds.
- **Measure before spending:** each tier starts only after the previous tier's real spend is checked against its estimate.

Estimates assume about 1.1k prompt tokens and 120 output tokens per call, with about 1.5 calls per question. M1 measures the real numbers; the tiers below are re-priced before tier 1 starts.

| Tier | Item | Estimate | Running total |
|---|---|---|---|
| 0 | Smoke test: 10 rows, measures the real cost per call | ~$0.10 | $0.10 |
| **1: core story** | R1 (no harness) | ~$0.50 | |
| | R2–R5 (one full-harness run; kimi-k3 only on misses) | ~$1.50 | |
| | Trace harvest: ~1,500 train questions, full harness | ~$7 | |
| | FT1, FT2, FT3 training | $0 | |
| | R6, R7, R8 evals (~$0.70 each) | ~$2 | **~$11** |
| **2: RL** | FT6: ~30 steps × 32 samples from the best SFT checkpoint (train at $5.86/M plus sampling) | ~$8–10 | |
| | R11 eval | ~$0.70 | **~$21** |
| **3: self-improving + cheap model** | FT4 round 2: ~1,000 new train questions through the best model; training free | ~$5 | |
| | R9 eval | ~$0.70 | |
| | R12: best recipe on Qwen 3.6 35B A3B (SFT at $2.14/M, plus eval) | ~$3 | **~$30** |
| **4: optional** | FT5 DPO: ~300 pairs (~$4–5), plus R10 eval | ~$5 | ~$35 |
| | Buffer for re-runs and price surprises | ~$10–15 | ≤ $45 |

Checks (a human confirms each one):
- **After tier 0:** if the real cost per call is more than 1.5× the estimate, re-price every tier and cut from the bottom.
- **After tier 1:** if spend is above $15, shrink FT6 to ~15 steps.
- **Before tier 4:** run FT5 only if spend is ≤ $30.
- **Any single step** expected to cost more than **$5** is confirmed first.

Never cut: R1, R2–R5, FT1–FT3. They carry the whole story on their own: harness beats frontier, traces beat gold.

## 12. Milestones

| # | Deliverable | Done when |
|---|---|---|
| M1 | `fw.py`, `tracing.py`, `retrieve.py`, `fixes.py`, `harness.py`, `run_eval.py`, tests | Tests pass. A 10-row smoke run writes a valid result file and shows up in Langfuse. |
| M2 | R1, plus a first dashboard showing the Pareto charts | Starting score on 200 rows is plotted. |
| M3 | R2–R5, plus `compare.py` | Harness curve with paired CIs, on the dashboard. |
| M4 | Verified gold train set; trace harvest; `build_sft.py` | Leak check reports 0 overlap for all three training files. |
| M5 | FT1, then R6 | Scored inside the harness. |
| M6 | FT2 → R7, FT3 → R8, FT4 → R9 | Scored. Stage chart shows the shift to "first". |
| M7 | FT6 (or FT5) → R11 (or R10); best recipe on Qwen 3.6 35B A3B → R12 | Scored, within the $45 cap. |
| M8 | Dashboard final, README numbers, demo script | Every number in the README traces back to a result file. |
| M9 (stretch) | CypherBench on 2–3 graphs | Run with its own scorer. |

## 13. Risks

| Risk | Mitigation |
|---|---|
| The public demo server goes down | Gold rows are snapshotted in `test.jsonl`. Predictions still need the server, so run the important rows early. |
| Muse Glimmer base not available at serverless rates | Use the training sampler, or switch the base model and say so. |
| Free training promo ends or doesn't apply | Re-check the docs before M5. |
| Langfuse free-tier limit | Local JSON is the source of truth. Mirror test runs fully and harvests partially, or self-host. |
| Gains under ~5 points aren't significant on 200 rows | Use paired tests; report the CI rather than only the point estimate. |
| Noisy gold queries | Hand-check cases where several configs return the same "wrong" rows. |
| Trace SFT overfits to the 5 graphs | Optional CypherBench check (M9) on unseen graphs. |

## 14. Out of scope

Voting over multiple samples, managed RFT (deprecated on Fireworks), custom RL, MCP tooling, GraphRAG-Bench, and running the frontier model ourselves.

## 15. Decisions log (as run, 2026-11-02)

| Time | Decision | Evidence |
|---|---|---|
| 12:05 | Escalation to kimi-k3 uses `reasoning_effort=low` and 2,048 max tokens | With 400 tokens it spent everything on hidden reasoning and returned nothing (smoke10, t009). With low effort it answers in ~120 tokens for ~$0.003. |
| 12:31 | Harness stages 2–4 add little on top of examples (R2 54.0% → R5 56.0%) | 83 of 92 R5 misses ran cleanly and returned wrong rows. The repair loop only fires on errors and empty results (9 cases). CypherGuard reports the same limit. |
| 12:35 | Added `--warn`: repair queries that run with database warnings (unknown property, label or relationship type) | Neo4j returns warnings for these, and our executor was ignoring them. |
| 12:46 | `--warn` **not used** on test | On the 200-question dev split (train questions, never test) only 1 first attempt had a warning; the accuracy change was +0.0%. |
| 12:46 | Harness design choices are made on `data/dev.jsonl`, never on the test set | Avoids tuning to the test set. |
| 12:48 | FT6 (RL) and FT4 (round 2) **cut for time** | SFT runs at ~25 s per step (FT1: 188 steps ≈ 80 min). With submissions closing at 16:30, only FT1–FT3 can train and be evaluated. |
| 12:47 | Harvest (1,500 train questions, R5 config): 50.7% solved, $3.96 | `results/harvest1.json`. 761 traces end in a correct query; 26 of them via repair or escalation. |
| 12:48 | Leak check now **drops and names** matching examples instead of aborting | It caught `p01475`: a train question paraphrasing test question "top 5 most expensive products supplied by 'Exotic Liquids'" with the identical answer. The pool filter only removed exact question matches. FT2/FT3 exclude it. FT1, already training, contains that row with the dataset's differently worded gold; R6 is also reported with that test question removed. |
| 12:48 | FT2 = 760 examples, FT3 = 785 (760 + 25 repair turns), FT1 = 1,500 | FT1 sees about twice as many examples as FT2, so FT1 vs FT2 compares data *sources* with unequal sizes. Stated as a caveat. |
| 12:51 | Clock check: my earlier time estimates ran ~35 min ahead of the real time | `date` |
| 12:55 | Only `muse-glimmer-30b` supports serverless training on this account (Qwen 3.6, GLM, Kimi and DeepSeek report `supportsServerlessTraining=False`), and it allows **one concurrent run** | Model API fields; HTTP 429 "in use 1, limit 1". FT2 and FT3 could not start alongside FT1. |
| 12:56 | FT3 dropped (only 25 repair turns on top of FT2). The second Muse slot goes to **FT-D: rejection-sampling distillation**, i.e. verified answers from Muse, gpt-oss-120b and glm-5p3 | Dev: each model solves 49–51% alone, their union 61%. |
| 12:53 | gpt-oss-120b + harness + escalation on test: **56.0% at $0.00042/question**, 0.93 s | `results/r13_gptoss.json`. Same accuracy as Muse R5 at ~1/6 of its cost. |
| 12:55 | Cross-model voting by result rows (`vote.py`) on dev: 3 cheap models → 53.0% at $0.0031/q (best single cheap 51.0%) | Offline re-execution of each run's final query; gold used only for grading. |
| 12:57 | **R6 (FT1 + harness) on test: 66.0%** (CI 59.2–72.2), $0.0026/q, 1.2 s. Cut at "first": 64.5% | `results/r6_ft1.json` |
| 12:58 | Contamination check: **R6 on the 111 test questions with no train paraphrase (word-overlap < 0.6) = 65.8%**, vs 66.3% on near-duplicates. R6 − R5 on the clean subset = +14.4 pts (CI +4.5 to +24.3, p = 0.007) | `contamination.py --train data/sft_ft1_gold.jsonl data/train.jsonl` |
| 12:59 | Cross-model vote on test (R6 + glm-5p3 + gpt-oss): **65.5%**, below R6 alone (66.0%) at ~2× its cost. Oracle (any model right) 76.5% | `results/r16_vote3.json`. Voting not used. |
| 13:02 | A LoRA checkpoint can still be sampled **after** its training session is deleted | Probe call on the FT1 checkpoint after `train.py cleanup --tag ft1` returned a normal reply. |
| 13:04 | Lenient metric (gold values contained in the answer, extra columns allowed) adds only 1–5 pts per config; the ranking is unchanged (R6 69.0% lenient) | `lenient.py`; strict stays the headline. |
| 13:06 | **FT-D (distillation) on test: 58.0%**, +2.0 vs R5 (n.s.), −8.0 vs FT1 (CI −14.5 to −1.0, p = 0.03). Clean subset +0.8 vs R5 | 760 of its 919 examples are queries Muse already got right (initial loss ~0.03). Gold SFT also covers the questions the model fails, which is where the gain comes from. |
| 13:11 | **Kimi K3 + harness on test: 63.0%**, $0.0051/q, 2.7 s. R6 (fine-tuned 30B) beats it at half the cost and ~2× the speed, on the same questions | `results/r17_kimi.json` |
| 13:11 | **FT1 with no retrieved examples (R6z): 63.5%** at $0.0022/q: fine-tuning mostly replaces retrieval | `results/r6z_ft1_noshots.json` |
| 13:11 | SFT steps now ~6–7 s (earlier ~25 s, likely shared-pool load); FT1-big ends ~13:35, leaving room for 2–3 more runs | `logs/train_ft1big.log` |
| 13:30 | **Eval-set validation.** Gold is stable (re-run matches stored rows, identical across two runs), no duplicate questions. All 45 unsolved items (44 no config solves, plus t182) reviewed by Claude Code (not humans): 5 gold_wrong, 20 ambiguous, 20 format_only, 0 pure model errors. On the 175 valid questions every config gains ~9 pts and **the ranking is unchanged**: R6 75.4%, Kimi 71.4%, glm 69.7%, R5 64.0%. R6 − R5 = +11.4 (CI +4.0 to +19.4, p = 0.006) | `data/test_audit.jsonl`, `validate_eval.py`. The frontier comparison stays on all 200 (the published number is on a similarly unreviewed subset). |
| 13:32 | **FT1-big (R6b): 65.5%**, same as FT1 (66.0%; −0.5, p = 1.0). 3× the gold data did not help. Final training loss 0.173 vs FT1's 0.128 (1 epoch vs 2) | `results/r6b_ft1big.json` |
| 13:32 | **Trace review of R6's 43 failures on the 175 validated questions:** ~30 return the same answer with different columns (the dataset has no consistent projection convention; similar questions get different gold columns), ~10 are genuine logic errors (wrong property, wrong relationship, wrong aggregate), ~3 are further tie/interpretation cases. More data stops helping because the remaining strict-metric errors are mostly unlearnable annotator choices. | Manual read of each failure with gold rows vs R6 rows |
| 13:32 | Vote R6 + R6b + Kimi K3 by result rows: **68.0%** strict (oracle 78.0%), $0.010/q, 2.7 s | `vote.py` |
| 13:42 | FT-KD resized to FT1's 1,500 gold + 131 Kimi K3 answers (questions Kimi solved and Muse failed), 2 epochs, so it compares directly with FT1. Added **FT-HF**: FT1's gold with the 739 trace-flagged failures doubled (2,239 examples, 2 epochs). Queue: FT-BX → FT-KD → FT-HF | Only 131 teacher examples qualified, 2% of FT-BX's data, too small to measure there |
| 13:42 | Rows now logged in traces: every `execute` step carries its first 5 rows, and the question node the final query, outcome and rows. All 9 test runs backfilled with `rows (<source>)` and `gold rows` steps (3,723) | `scripts/backfill_rows.py` |
| 13:56 | **Retrieval on dev (FT1 model, full harness): keyword top 3 = 58.0% is best.** Keyword top 5 / 10: 57.0% / 56.0%. Embedding (qwen3-embedding-8b, cosine) top 3 / 5 / 10: 57.0% / 55.5% / 56.5%. All differences n.s. (p ≥ 0.36); more examples cost up to +37%/q. Kept keyword top 3 | `results/dev_ft1_*.json`. Caveat: FT1 was trained on keyword top-3 prompts. Embeddings cost $0.0018 in total. |
| 14:03 | **FT-BX (R6bx): 68.5%** (CI 61.8–74.5), best single model so far. +2.5 vs R6 (n.s., p = 0.40); +3.0 vs FT1-big, which had the same in-domain data without the 9 other graphs. Clean subset 68.8%, validated 77.1%. First attempt alone: 67.0% | `results/r6bx_ftbx.json` |
| 14:03 | Vote of three Muse-only adapters (R6 + R6b + R6z) on test: 70.0% (CI 63.3–75.9), $0.0075/q. **Chosen after trying combinations on test**, so the ensemble choice is being re-made on dev (all 3/4-way combos of R6, R6b, R6z, R7d, R6bx) and only that choice is reported | `results/r19_vote_muse.json`, `dev_*` runs |
| 14:16 | **Ensemble chosen on dev** (best of 15 three- and four-way combos of R6, R6b, R6z, R7d, R6bx): R6 + R6b + R7d + R6bx, dev 59.5% vs best single on dev 58.0%. **On test: 68.0%**, same as FT-BX alone (68.5%, p = 1.0). The test-selected trio's 70.0% (R19) is not citable. Ensembling doesn't reliably beat the best single adapter here | `results/r20_vote_devpick.json`; `/private/tmp/claude-501/dev_vote.py` output |
| 14:16 | **Headline: FT-BX single model, 68.5%** (+11.9 over published 56.6%), $0.0026/q, 1.1 s; clean subset 68.8%, validated 77.1% | — |
| 14:20 | **FT-KD (R6kd): 65.5%**, same as FT1 (−0.5, p = 1.0); validated 74.9%, clean 65.8%. 131 Kimi K3 answers on Muse's failures (~8% extra data) made no measurable difference: gold is already the best teacher here | `results/r6kd_ftkd.json` |
| 14:30 | **Examples in context, untuned Muse 30B (dev, examples only):** 0 / 3 / 5 / 10 keyword = 46.5 / 48.0 / 49.5 / 53.0%; embedding 3 / 5 / 10 = 50.0 / 49.5 / 53.0%. 0 → 10 = +6.5 (p ≈ 0.07–0.09). After fine-tuning, extra examples don't help (FT1: 58.0 → 56.0%) and cost more: examples partly substitute for SFT | `results/dev_base_*.json` |
| 14:30 | Nemotron-lightning (3B active): every call hit the 2,048-token cap on hidden reasoning at effort=low; restarted with reasoning_effort=none | ledger rows for r21_nemotron |
| 14:30 | `dashboard/why.py` → `why.png`: head-to-head wins (base vs harness, base vs SFT, Kimi K3 proxy vs FT-BX, FT-D vs FT1) split by the loser's failure type, plus accuracy by tier | — |
| 14:36 | **Nemotron Lightning (3B active) dropped: broken on Fireworks.** reasoning_effort=none returns degenerate text ("MATCH (m) (m) (m)…") after 292 s; low returns nothing after 171 s. Deprecated 2026-11-07 per the model API | probe calls; `logs/r21_nemotron.log` |
| 14:36 | Added a free local backend (`fw.LocalHF`, Apple GPU via MPS). Running **Qwen2.5-1.5B-Instruct, untuned**, with the harness (examples, fix, repair; no escalation) on test, ~4–6 s per call | `results/r22_qwen15.json` (pending) |
| 14:51 | **FT-HF (R6hf): 61.0%**, −5.0 vs FT1 (n.s. on all 200); validated −7.4 and clean subset −9.0 (both p = 0.03). Near-duplicates are unchanged (66.3%) while clean questions drop to 56.8%: doubling trace-flagged failures doubled label noise (many training "failures" have wrong or ambiguous gold) | `results/r6hf_fthf.json` |
| 14:52 | Local Qwen2.5-1.5B with the repair loop ran too slowly (40/200 in ~15 min, finish ~16:05). Restarted with examples + arrow fix only (no repair); compare with the untuned Muse 30B "examples only" row (54.0%) | `logs/r22_qwen15.log` |
