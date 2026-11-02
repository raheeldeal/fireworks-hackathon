#!/bin/sh
# Regenerates BASELINES.md from results/*.json
cd "$(dirname "$0")/.."
{
cat <<'HDR'
# Text-to-Cypher baselines

Test set: `data/test.jsonl`, 200 rows from the official TEST split of `neo4j/text2cypher-2025v1`, sha256 `6c47ee00573e7ebc4e144c7e31363b2f3c72b10556e5d2c853323cc85733b491` (`data/TEST_HASH`). 40 rows per graph (movies, recommendations, northwind, fincen, twitter), executed live on `neo4j+s://demo.neo4jlabs.com`.
Prompt: `prompts/v1_plain.txt` (the graph's schema text, then "Return only the Cypher query"). Temperature 0, max_tokens 4096, default reasoning except nemotron (`reasoning_effort: "none"`). One seed.
Sanity check: re-executing the gold queries scores 200/200 (`results/gold_v1_plain_n200.json`), so the server is deterministic for this set. The 2025v1 gold Cypher stores line breaks as a literal backslash + n; the executor turns them into real line breaks at run time (stored rows untouched).

Chart: `baselines.png` (solid bar = strict, dashed outline = lenient, $/1k under each bar).

**Strict** = the predicted result set equals the gold result set as an unordered multiset of rows (column names and column order ignored, floats to 3 dp).
**Lenient** = strict, plus a row counts when the prediction returns extra columns, or returns properties where gold returned whole nodes. Row counts must still match. Strict is the headline number; lenient shows how much of the gap is projection style rather than wrong logic.
error = query failed to run (syntax, unknown function, timeout) or no query returned; empty = ran but returned no rows; wrong = rows differ.

HDR
.venv/bin/python scripts/summarize.py
cat <<'FTR'

## Reading the numbers
- Most misses are "wrong", not "error": models write valid Cypher that answers a slightly different question (extra or missing columns, returning a node instead of a name, a different interpretation of "top"). Execution errors are 0 to 2%.
- 17 test rows use LIMIT without ORDER BY, so the gold rows are arbitrary ("list 3 movies..."). A correct query can return different rows.
- The frontier models do not win on this prompt. glm-5p3 and kimi-k3 think by default; with max_tokens 4096 a few calls ran out of tokens mid-thought (the `truncated` count in each results file) and returned no query, which counts as an error.
- glm-5p3 and kimi-k3 were run on the first 100 rows only (cost); use the "same first 100 rows" table for model-to-model comparisons.

Regenerate: `sh scripts/write_baselines.sh`
FTR
} > BASELINES.md
