# Text-to-Cypher benchmark: status

Updated 12:55 PT.

## Done
1. **Dataset: `neo4j/text2cypher-2025v1`** (team standard as of 11:25). Columns: question, schema, cypher, data_source, instance_id, database_reference_alias. Raw copies in `raw/`. The earlier 2024v1 set and its baselines are kept in `data/old_2024v1/` and `results/old_2024v1/` for reference only.
2. **Executor backend: the live public Neo4j demo server** (`neo4j+s://demo.neo4jlabs.com`, user = password = database name). All five graphs answer in about 1 s per query, so no kuzu fallback. Writes are rejected (tested: `CREATE` fails with an access-mode error).
3. **Graphs:** movies, recommendations, northwind, fincen, twitter.
4. **Executor** (`executor.py`): read-only transaction, 10 s server timeout, returns rows or an error string, caps at 1,000 rows.
5. **Scorer** (`score.py`): compares result sets as unordered multisets of rows; ignores column names and column order; rounds floats to 3 decimals; treats collect() lists as unordered. Returns correct / wrong / error / empty. A second, lenient metric also accepts extra columns, or properties where gold returned whole nodes (row counts must still match). `test_score.py`: 16 pytest cases pass.
6. **Complexity tags** per gold query: hops, variable-length paths, aggregation, WHERE, ORDER BY, LIMIT. Tier: easy (0 to 1 hop, no aggregation), medium (multi-hop or aggregation), hard (both).
7. **Test set locked** (`data/test.jsonl`, 200 rows, from the 2025v1 official TEST split only).
   - sha256 `6c47ee00573e7ebc4e144c7e31363b2f3c72b10556e5d2c853323cc85733b491` (also in `data/TEST_HASH`).
   - 40 rows per graph. Tiers: 70 easy, 87 medium, 43 hard. 65% multi-hop or aggregation (target 25%+).
   - Every gold query ran on the live server and returned 1 to 200 rows in under 8 s; gold rows stored per line (`gold_result`); source `instance_id` stored as `source_id`.
   - Purity check: question, cypher and schema in all 200 rows are byte-identical to the Hugging Face rows. Re-running the gold queries scores 200/200.
8. **Train set** (`data/train.jsonl`, 500 rows, 100 per graph) from the 2025v1 TRAIN split, gold verified the same way, any question or gold query also in test removed. `check_leak.py`: 0 overlap.

9. **Baselines done** on the 2025v1 set. Full tables in `BASELINES.md`, chart in `baselines.png`, per-row results in `results/<model>_v1_plain*_n*.json` (standard shape plus pred_cypher, exec_status, lenient_status, latency, in/out/reasoning tokens).

| model | n | strict | lenient | error | $/1k |
|---|---|---|---|---|---|
| glm-5p3-flash | 200 | 57.0% | 69.5% | 0.5% | $0.24 |
| deepseek-v4p1-flash | 200 | 49.0% | 64.0% | 1.5% | $0.82 |
| kimi-k3 (frontier) | 100 | 49.0% | 61.0% | 2.0% | $6.36 |
| glm-5p3 | 100 | 48.0% | 62.0% | 3.0% | $3.13 |
| nemotron-lightning, reasoning off | 200 | 22.5% | 29.5% | 32.0% | $0.08 |

   On the same first 100 rows: glm-5p3-flash 58%, kimi-k3 49%, glm-5p3 48%, deepseek 47%. 33 of those 100 rows are missed by every model.
10. **Spend:** about $2.26 from this workstream (includes $0.04 of estimated usage for two killed nemotron runs). `ledger.csv` reads $2.79 because other team runs also append to it since 12:32.

## What a human must decide
- **2025v1 gold Cypher has a formatting defect.** In 4,427 of 4,438 test rows the line breaks are stored as the two characters backslash + n, so the raw gold fails with a syntax error on Neo4j. The executor converts them back to real line breaks at run time (`executor.normalize_cypher`); the stored rows are untouched. Inside Cypher strings the escape and a real line break mean the same thing, so no query changes meaning. If you want a zero-normalization rule, the 2025v1 gold set cannot run as published.
- **2025v1 test is the 2024v1 test, reformatted.** All 4,433 shared instance ids have identical Cypher once the line breaks are fixed. Our new 200 rows share 100 questions with the old locked 200. Fine to cite either; do not report both as independent benchmarks.

## Caveats
- Questions are mostly synthetic (GPT-4o, Gemini, Claude Opus, GPT-4 Turbo) plus 9 crowdsourced rows. Some gold queries are imperfect; a hand-checked hard slice would fix that.
- 17 test rows use LIMIT without ORDER BY, so the gold rows are arbitrary picks; a correct query can return different rows.
- The demo server is shared and public. If Neo4j takes it down during judging, prediction scoring stops. Gold rows are snapshotted in test.jsonl.
- nemotron-lightning's endpoint hung on about 1 in 5 requests today. The runner now has `--timeout` (25 s used) and records wall time including retries. 4 rows still failed at the API and count as errors.
- The tier labels do not track difficulty the way you would expect: "easy" rows score lowest for every model. Easy questions often ask for "the movies" or "3 users", and the gold picks one projection (whole node vs. name) or arbitrary rows. A human hard-slice review would separate real model errors from gold ambiguity.
- `results/` also holds other agents' files (harness_*, train_*, *_rlow_*, a failed claude-opus-5 run at 0%). BASELINES.md and baselines.png read only the five baseline files above.
