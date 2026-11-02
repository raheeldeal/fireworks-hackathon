# Text-to-Cypher on open models: a benchmark that executes, a harness that knows when to stop, and a free fine-tune that beats the priciest model

Fireworks "Make your own frontier" hackathon, 2 Nov 2026.

**One line:** an analyst asks a question in English, we generate Cypher, run it on a real Neo4j graph, and return rows. Graded by execution, not by string match.

## Headline numbers
| Setup | Accuracy | $ / 1k |
|---|---|---|
| kimi-k3 (priciest open model) | 50.0% | $6.36 |
| glm-5p3-flash (cheapest small) | **60.5%** | **$0.24** |
| Muse Glimmer 30B base | 51.5% | — |
| **30B + SFT + RFT (ours, free training)** | **60.0%** | $0.25 served |
| small + harness with routing | 59.0% (67.0% column-tolerant) | $0.77 |

Three findings, with the evidence in `RESULTS_FINAL.md`:
1. **Price does not buy accuracy here.** Three expensive models sit at 49 to 53%; the cheapest is at 60.5%. We eliminated scorer strictness, column tolerance and reasoning budget as explanations.
2. **Fine-tuning on execution reward works.** 51.5% → 59.0% (SFT) → 60.0% (RFT), training free. The advantage-weighted RFT variant regressed to 36.5%; diagnosed and documented rather than dropped.
3. **~15% of the public benchmark is mis-keyed.** Of 36 easy-tier "failures", the model is genuinely wrong twice. Audit in `audit/MISS_AUDIT.md`.

## The benchmark
- 200 questions from the public `neo4j/text2cypher-2025v1` **test** split, 40 from each of five live Neo4j demo graphs.
- Every gold query executed on the live graph; its rows are the answer key (stored per row).
- Locked: `data/TEST_HASH` = `6c47ee00573e7ebc4e144c7e31363b2f3c72b10556e5d2c853323cc85733b491`, re-verified at the start of every run.
- Training: 500 rows from the **train** split only. Zero overlap, verified by `../runs/common/check_leak.py`.
- Grader: execution accuracy with result-set equality, rules and justifications in `audit/SCORING.md`, **31 unit tests** in `test_score.py`.

## The harness (`harness/`)
`validate` (read-only, labels and properties exist in the schema) → `generate` → `execute` → `repair` once from the error text → `vote3` (three attempts, majority by executed rows) → `route` (escalate only when no two agree) → `schema_prune` (optional).

It does not raise accuracy. It makes the system shippable: broken queries 2.2% → 0.1%, and agreement across three executed attempts is a usable confidence signal (unanimous 64.8% correct, split 35%, disagree 17.7%). Calibration in `harness/CALIBRATION.md`.

## Fine-tuning (`train/`)
LoRA on Muse Glimmer 30B through the Fireworks **Training API** (no dataset upload, no deployment). SFT on 500 execution-verified rows, then RFT by rejection sampling where the reward is "the query's rows match gold". `train/TRAIN.md` has the reward function and the full write-up including the failed variant. Saved model: `accounts/raheeldeal/models/cypher-sft-1150`.

## Observability (`trace/`)
Every question traced to Langfuse: schema pruning, each generation (prompt, reply, tokens, cost), validation problems, execution (exact Cypher, status, rows, errors), repair, vote agreement, routing. Default off, so scored runs are unaffected. `trace/README.md` for the dashboard.

## Reproduce
```bash
export FIREWORKS_API_KEY=...
pip install -r requirements.txt   # neo4j driver, matplotlib
pytest test_score.py                                            # 31 tests
python3 run_eval.py --model accounts/fireworks/models/glm-5p3-flash --prompt prompts/v1_plain.txt
python3 harness/run_harness.py --config route_big
python3 audit/superset_test.py                                  # column-tolerant re-score
python3 make_charts.py                                          # frontier.png, coverage.png
```

## Layout
`data/` locked exam + training rows · `executor.py` read-only Cypher runner · `score.py` graders · `harness/` the harness · `train/` fine-tuning · `audit/` scorer audit, miss taxonomy, re-scoring · `trace/` Langfuse · `review/` eval-set review sheet for human annotators · `RESULTS_FINAL.md` · `BUSINESS.md` · `PITCH.md` · `TEAM.md`
