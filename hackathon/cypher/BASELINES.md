# Text-to-Cypher baselines

Test set: `data/test.jsonl`, 200 rows from the official TEST split of `neo4j/text2cypher-2025v1`, sha256 `6c47ee00573e7ebc4e144c7e31363b2f3c72b10556e5d2c853323cc85733b491` (`data/TEST_HASH`). 40 rows per graph (movies, recommendations, northwind, fincen, twitter), executed live on `neo4j+s://demo.neo4jlabs.com`.
Prompt: `prompts/v1_plain.txt` (the graph's schema text, then "Return only the Cypher query"). Temperature 0, max_tokens 4096, default reasoning except nemotron (`reasoning_effort: "none"`). One seed.
Sanity check: re-executing the gold queries scores 200/200 (`results/gold_v1_plain_n200.json`), so the server is deterministic for this set. The 2025v1 gold Cypher stores line breaks as a literal backslash + n; the executor turns them into real line breaks at run time (stored rows untouched).

Chart: `baselines.png` (solid bar = strict, dashed outline = lenient, $/1k under each bar).

**Strict** = the predicted result set equals the gold result set as an unordered multiset of rows (column names and column order ignored, floats to 3 dp).
**Lenient** = strict, plus a row counts when the prediction returns extra columns, or returns properties where gold returned whole nodes. Row counts must still match. Strict is the headline number; lenient shows how much of the gap is projection style rather than wrong logic.
error = query failed to run (syntax, unknown function, timeout) or no query returned; empty = ran but returned no rows; wrong = rows differ.

| model | config | n | accuracy (strict) | accuracy (lenient) | wrong | error | empty | p50 s | p95 s | $/1k | out tok/row | reasoning tok/row |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| glm-5p3-flash | v1_plain | 200 | 57.0% | 69.5% | 42.0% | 0.5% | 0.5% | 1.62 | 4.31 | $0.241 | 230 | 186 |
| deepseek-v4p1-flash | v1_plain | 200 | 49.0% | 64.0% | 48.5% | 1.5% | 1.0% | 2.12 | 11.77 | $0.820 | 461 | 412 |
| kimi-k3 | v1_plain | 100 | 49.0% | 61.0% | 48.0% | 2.0% | 1.0% | 3.41 | 11.01 | $6.363 | 261 | 205 |
| glm-5p3 | v1_plain | 100 | 48.0% | 62.0% | 48.0% | 3.0% | 1.0% | 2.51 | 11.93 | $3.128 | 454 | 407 |

**Accuracy by graph**

| model | n | movies | recommendations | northwind | fincen | twitter |
|---|---|---|---|---|---|---|
| glm-5p3-flash | 200 | 70% (40) | 55% (40) | 57% (40) | 57% (40) | 45% (40) |
| deepseek-v4p1-flash | 200 | 62% (40) | 42% (40) | 48% (40) | 57% (40) | 35% (40) |
| kimi-k3 | 100 | 65% (23) | 50% (20) | 44% (16) | 53% (19) | 32% (22) |
| glm-5p3 | 100 | 74% (23) | 45% (20) | 44% (16) | 53% (19) | 23% (22) |

**Accuracy by complexity tier** (easy: 0 to 1 hop, no aggregation; medium: multi-hop or aggregation; hard: both)

| model | easy | medium | hard |
|---|---|---|---|
| glm-5p3-flash | 49% (70) | 61% (87) | 63% (43) |
| deepseek-v4p1-flash | 44% (70) | 54% (87) | 47% (43) |
| kimi-k3 | 40% (35) | 63% (43) | 36% (22) |
| glm-5p3 | 34% (35) | 60% (43) | 45% (22) |

**Apples to apples: all models on the same first 100 test rows**

| model | strict (first 100) | lenient (first 100) |
|---|---|---|
| glm-5p3-flash | 58% | 68% |
| deepseek-v4p1-flash | 47% | 60% |
| kimi-k3 | 49% | 61% |
| glm-5p3 | 48% | 62% |

On the first 100 rows, 36 rows are missed by every model; 64 are solved by at least one model (oracle ceiling).

Ledger total: $2.2317

## Reading the numbers
- Most misses are "wrong", not "error": models write valid Cypher that answers a slightly different question (extra or missing columns, returning a node instead of a name, a different interpretation of "top"). Execution errors are 0 to 2%.
- 17 test rows use LIMIT without ORDER BY, so the gold rows are arbitrary ("list 3 movies..."). A correct query can return different rows.
- The frontier models do not win on this prompt. glm-5p3 and kimi-k3 think by default; with max_tokens 4096 a few calls ran out of tokens mid-thought (the `truncated` count in each results file) and returned no query, which counts as an error.
- glm-5p3 and kimi-k3 were run on the first 100 rows only (cost); use the "same first 100 rows" table for model-to-model comparisons.

Regenerate: `sh scripts/write_baselines.sh`
