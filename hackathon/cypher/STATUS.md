# Text-to-Cypher benchmark: status

Updated 10:44 PT.

## Done
1. **Data.** Downloaded `neo4j/text2cypher-2024v1` from Hugging Face (39,554 train / 4,833 test rows; columns: question, schema, cypher, data_source, instance_id, database_reference_alias). Raw copies in `raw/`.
2. **Executor backend: the live public Neo4j demo server** (`neo4j+s://demo.neo4jlabs.com`, user = password = database name). All five chosen graphs answer in about 1 s per query, so no kuzu fallback was needed. Writes are rejected (tested: `CREATE` fails with an access-mode error).
3. **Graphs chosen:** movies, recommendations, northwind, fincen, twitter.
4. **Executor** (`executor.py`): read-only transaction, 10 s server timeout, returns rows or an error string. Caps at 1,000 rows.
5. **Scorer** (`score.py`): compares result sets as unordered multisets of rows; ignores column names and column order; rounds floats to 3 decimals; treats collect() lists as unordered. Returns correct / wrong / error / empty. `test_score.py`: 12 pytest cases pass.
6. **Complexity tags** per gold query: hops, variable-length paths, aggregation, WHERE filters, ORDER BY, LIMIT; tier = easy (0 to 1 hop, no aggregation), medium (multi-hop or aggregation), hard (both).
7. **Test set locked** (`data/test.jsonl`, 200 rows). sha256 `165146bffa05ae1b1b49115b6df7aeea8e1f5f4bd7089d784c3f7ea373ce1b14` (also in `data/TEST_HASH`). Drawn only from the dataset's official test split. Every gold query ran on the live server and returned 1 to 200 rows in under 8 s; the gold rows are stored in each line (`gold_result`).
   - 40 rows per graph. Tiers: 70 easy, 86 medium, 44 hard (movies has only 4 hard candidates, so it has 22 medium).
   - 65% multi-hop or aggregation (target was 25%+). 67 multi-hop, 107 with aggregation.
8. **Train set** (`data/train.jsonl`, 500 rows, 100 per graph) from the dataset's train split, gold verified the same way, with any question or gold query that appears in test removed. `check_leak.py`: 0 overlap.

## Next
Baselines, harness and fine-tunes: done or running. See [README.md](README.md) for results and [HARNESS.md](HARNESS.md) §15 for the decisions log.

Final status (15:00):
- **Best single model:** Muse Glimmer 30B + LoRA SFT on 6.5k verified gold (5 graphs + 9 other graphs), R6bx: **68.5%** strict on the 200 test questions (published frontier: 56.6%). 77.1% on the 175 audited-fair questions; 68.8% on the clean (no-paraphrase) subset.
- **Tested, not adopted:** RFT-style self-distillation (58.0%), teacher distillation (65.5%), hard-example upweighting (61.0%), voting chosen on dev (68.0%), database-warning repair, embedding retrieval and more in-context examples (dev).
- **Charts:** `dashboard/waterfall.png`, `before_after.png`, `why.png` (+ `_valid` versions); dashboard `dashboard/index.html`.
- **Spend:** about $33 of the $45 cap.

## What a human must do
- Decide when to commit to `main`.
- Rotate the Fireworks and Langfuse secret keys after the hackathon (both were pasted into a chat).

## Caveats
- The questions are synthetic (written by GPT-4o, Gemini, Claude Opus, GPT-4 Turbo) plus 8 crowdsourced rows. Some gold queries are imperfect; a hand-checked hard slice would fix that.
- The demo server is shared and public. If Neo4j takes it down during judging, scoring stops working. Gold rows are snapshotted in test.jsonl, but predictions still need a live server.
