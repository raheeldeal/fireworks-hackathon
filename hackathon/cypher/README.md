# Text-to-Cypher

An analyst asks a question in English; the system returns the right rows from a Neo4j graph, checked by running the query.
The aim is to match a frontier model's accuracy with an open model plus a harness, at a fraction of the cost.

- Plan for the harness, training and dashboard: [HARNESS.md](HARNESS.md)
- Benchmark status and test-set details: [STATUS.md](STATUS.md)
- Hackathon plan and judging: [PLAN.md](PLAN.md)

## Data

| | |
|---|---|
| Source | [`neo4j/text2cypher-2024v1`](https://huggingface.co/datasets/neo4j/text2cypher-2024v1) |
| Graphs | movies, recommendations, northwind, fincen, twitter, on the public read-only server `neo4j+s://demo.neo4jlabs.com` |
| Test set | `data/test.jsonl`: 200 rows (40 per graph), from the dataset's test split only. sha256 in `data/TEST_HASH`. Gold rows stored per line. |
| Train set | `data/train.jsonl`: 500 rows, leak-checked against test. `raw/` holds the full download: 8,379 train rows for these 5 graphs (gitignored). |

## Scoring

`score.py` runs nothing itself. It compares the rows a predicted query returned with the gold rows:
- Rows are compared as unordered multisets.
- Column names are ignored and floats are rounded to 3 decimals.
- The result is one of `correct`, `wrong`, `error` (the query failed) or `empty` (no rows when gold has rows).

This is the same execution-accuracy idea used by CypherBench and CypherGuard. We don't use BLEU or LLM judges.

## Setup

Run from the repo root (Python 3.11, [uv](https://docs.astral.sh/uv/)):

```bash
uv venv .venv --python 3.11
uv pip install --python .venv/bin/python neo4j datasets pytest
# Secrets go in hackathon/cypher/.env (git-ignored): FIREWORKS_API_KEY, LANGFUSE_PUBLIC_KEY, LANGFUSE_SECRET_KEY, LANGFUSE_BASE_URL
uv pip install --python .venv/bin/python langfuse==5.1.0
```

## Code

| File | What it does |
|---|---|
| `executor.py` | Runs a query read-only on the demo server. Returns rows, error and database warnings. |
| `score.py` | Grades a result against gold rows: `correct` / `wrong` / `error` / `empty`. |
| `fw.py` | Fireworks access: serverless chat (kimi-k3) and the training sampler (Muse Glimmer base and LoRA checkpoints). Spend ledger with a hard cap of $45. |
| `retrieve.py` | Picks the K most similar solved train questions from the same graph (keyword overlap). |
| `fixes.py` | Checks that need no model call: arrow-direction fix, schema hints, value lookups. |
| `harness.py` | The harness: examples → model → execute → arrow fix → repair loop → escalation. Never sees gold. |
| `tracing.py` | Langfuse tracing, one trace per question. A no-op without keys. |
| `run_eval.py` | Runs one config over a question file, grades every attempt, writes `results/<tag>.json`. |
| `metrics.py` | Summaries, and reading a full-harness run at an earlier stage (one run gives R2–R5). |
| `compare.py` | Paired comparison of two configs: bootstrap 95% CI plus exact McNemar test. |
| `scripts/build_pool.py` | Verifies every train gold query and writes the disjoint train splits. |
| `build_sft.py` | Writes SFT files for FT1 (gold), FT2 (traces) and FT3 (traces + repairs), with a leak check. |
| `train.py` | LoRA SFT on Muse Glimmer 30B through the Fireworks Serverless Training API. |
| `dashboard/build.py` | Builds `dashboard/index.html` from the result files. |

## Commands

Run from `hackathon/cypher/`, with `P=../../.venv/bin/python`. Keys live in `.env`.

```bash
$P executor.py                                    # ping all 5 graphs; last line shows writes are rejected
$P -m pytest -q test_score.py test_harness.py     # 30 offline unit tests
mkdir -p raw && $P scripts/download.py neo4j/text2cypher-2024v1    # full dataset into raw/
$P scripts/build_pool.py                          # verify train gold, write train_pool / harvest1 / harvest2 / rl_prompts / dev

# R1, then R2-R5 from one full-harness run
$P run_eval.py --tag r1_base
$P run_eval.py --tag r5_full --shots 3 --fix --repair 3 --escalate kimi-k3
$P compare.py results/r1_base.json results/r5_full.json:first     # any file can be read at a stage: first|fix|repair|escalate

# training data and fine-tunes
$P run_eval.py --tag harvest1 --data data/harvest1.jsonl --split train --shots 3 --fix --repair 3 --escalate kimi-k3
$P build_sft.py gold    --rows data/harvest1.jsonl --out data/sft_ft1_gold.jsonl
$P build_sft.py traces  --rows data/harvest1.jsonl --results results/harvest1.json --out data/sft_ft2_traces.jsonl
$P build_sft.py repairs --rows data/harvest1.jsonl --results results/harvest1.json --out data/sft_ft3_repairs.jsonl
$P train.py sft --data data/sft_ft1_gold.jsonl --tag ft1            # prints the checkpoint path
$P run_eval.py --tag r6_ft1 --model-path <checkpoint> --shots 3 --fix --repair 3 --escalate kimi-k3

$P dashboard/build.py                             # then open dashboard/index.html
```

Plan, story and decisions log: [HARNESS.md](HARNESS.md).

## Reference numbers (published, not run by us)

| System | Execution accuracy | Source |
|---|---|---|
| claude-sonnet-4.6, zero-shot | 56.63% | CypherGuard, Neo4j Text2Cypher audited subset, n=1,003 |
| claude-sonnet-4.6 + CypherGuard | 62.51% | same |
| gpt-5.4-mini, zero-shot | 47.36% | same |
| gpt-5.4-mini + CypherGuard | 56.33% | same |

Source: [CypherGuard](https://arxiv.org/html/2610.41755). It uses a different subset of the same dataset than our 200-row test set, so treat these as reference points, not a direct comparison.
