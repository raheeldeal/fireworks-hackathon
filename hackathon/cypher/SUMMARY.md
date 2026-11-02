# Where we are (updated 11:20 PT, Nov 2)

**Submission:** text-to-Cypher. Plain-English question → Cypher query → executed on a real Neo4j graph → rows. Judged 40% benchmark, 25% business value, 20% technical execution, 10% demo, 5% docs.

**Benchmark.** 200 questions from the public `neo4j/text2cypher-2025v1` test split (rebuild in progress from 2024v1; same procedure), 40 per graph across movies, recommendations, northwind, fincen, twitter. Every gold query executed on the live public demo server and its rows stored as the answer key. Scored by result-set equality (unit-tested, 12 cases). Locked and sha256-fingerprinted (`data/TEST_HASH`). Nothing is added to or changed in the public data. Tiers easy/medium/hard by query complexity.

**Baselines (running now).** glm-5p3-flash, nemotron (reasoning off), deepseek-v4p1-flash on all 200; glm-5p3 and kimi-k3 (frontier) on 100. Output: `BASELINES.md` and `baselines.png` (bars sorted upward, cost under each).

**Harness (being built now, `harness/`).** Elements, each scored on the locked set: validation (read-only, labels/properties exist in schema) → generate and repair once using the execution error → vote of three by executed result → route to the big model on disagreement → schema pruning. Calibration table shows accuracy by agreement level. Output: `HARNESS.md`, results in `results/harness_*.json`.

**Fine-tuning.** Training data: the public dataset's train split only (500 rows, execution-verified, zero overlap with test). SFT and RFT both through the Fireworks Training API (no dataset upload needed; managed RFT is not available today). RFT = sample candidates, reward 1 if execution matches gold, train on rewarded samples, repeat. Tuned model goes back inside the harness.

**Still to do.** Fine-tune runs (Eng 2 with Claude), deploy tuned model for demo (needs credits), ablation chart, business slide (cost per correct answer at 2,000 questions/day), pitch, README, submit by 15:45.

**Ask Fireworks staff.** Does the Training API accept per-sample weights (for weighted RL) or plain SFT steps only? Event credits for a two-hour dedicated deployment?

**How to work in this repo.** `git pull` before every push; four people on `main`. Work in `hackathon/cypher/`. Read `STATUS.md` (benchmark) and `harness/STATUS.md` (harness) for live progress.
