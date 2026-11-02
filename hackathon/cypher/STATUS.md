# Text-to-Cypher benchmark: status

Updated 11:30 PT.

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

## In progress
Baselines on the 2025v1 set (five models). BASELINES.md and baselines.png follow.

## What a human must decide
- **2025v1 gold Cypher has a formatting defect.** In 4,427 of 4,438 test rows the line breaks are stored as the two characters backslash + n, so the raw gold fails with a syntax error on Neo4j. The executor converts them back to real line breaks at run time (`executor.normalize_cypher`); the stored rows are untouched. Inside Cypher strings the escape and a real line break mean the same thing, so no query changes meaning. If you want a zero-normalization rule, the 2025v1 gold set cannot run as published.
- **2025v1 test is the 2024v1 test, reformatted.** All 4,433 shared instance ids have identical Cypher once the line breaks are fixed. Our new 200 rows share 100 questions with the old locked 200. Fine to cite either; do not report both as independent benchmarks.

## Caveats
- Questions are mostly synthetic (GPT-4o, Gemini, Claude Opus, GPT-4 Turbo) plus 9 crowdsourced rows. Some gold queries are imperfect; a hand-checked hard slice would fix that.
- 17 test rows use LIMIT without ORDER BY, so the gold rows are arbitrary picks; a correct query can return different rows.
- The demo server is shared and public. If Neo4j takes it down during judging, prediction scoring stops. Gold rows are snapshotted in test.jsonl.
- nemotron-lightning answered slowly today (50 to 65 s per call, even for "say hi").
