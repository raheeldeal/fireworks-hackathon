# Text-to-Cypher: plan (Nov 2, submissions close 16:30)

**One line.** An analyst asks a question in English; the system returns the right rows from a graph database, verified by execution, at a fraction of frontier cost.

**Why this task.** Frontier models score ~78% on published text-to-Cypher benchmarks; our overnight study of 10 tasks showed the frontier buys nothing on easy tasks, so we chose the hard one. Scoring is executable (run the query, compare rows), public data exists (Neo4j text2cypher), real graphs are public.

## Judging weights and what we deliver
- **Benchmark 40%.** 200-row locked test set across 4 to 5 real graphs, hash published, every gold query verified to execute. Scored by result-set equality. Difficulty tiers by query complexity. 30-row hard slice labeled by two humans, agreement and noise ceiling stated. 30 adversarial questions. 3 seeds per config. Scorer unit-tested. Frontier model run on the same set by us.
- **Business value 25%.** Buyer: analyst teams on fraud / supply-chain / identity graphs who wait on engineers for queries. Workload 2,000 questions/day. Metric: cost per *correct* answer and analyst minutes saved, frontier vs ours.
- **Technical execution 20%.** Harness: schema retrieval → small model → execute-and-repair → vote by execution → confidence routing to the large model. Then fine-tune on harness-verified queries (RFT with execution as reward if uploads work, else SFT via serverless training). Tuned model goes back inside the harness. Ablation curve: each component's cost and accuracy.
- **Demo 10%.** Live question → Cypher → execution error → repair → correct rows from a real graph. Same question to the frontier model: wrong query, full confidence.
- **Docs 5%.** README reproduces every number; hash; tests.

## Roles
- Raheel: eval owner, hard-slice labeling, business slide, pitch, clock.
- Eng 1: harness (executor, repair, vote, routing), each component scored before the next.
- Eng 2: Fireworks (uploads, credits, deploy), training file from verified queries, SFT/RFT job, deploy, demo recording.
- Claude: data, executor, scorer, baselines, eval pack, charts, docs, parallel fine-tune.

## Gates
- 11:30 executor runs, test set locked, baselines exist. Else cut to 3 graphs.
- 13:00 harness curve has 4+ points; fine-tune running or declared out.
- 14:30 everything on disk; no new experiments. Deploy done.
- 15:45 submit. 16:30 close.

## Folder
`hackathon/cypher/`: `STATUS.md` (live), `data/test.jsonl` + `TEST_HASH`, `executor.py`, `score.py`, `results/`, `BASELINES.md`, later `HARNESS.md`, `frontier.png`, `BUSINESS.md`, `PITCH.md`, `README.md`.
