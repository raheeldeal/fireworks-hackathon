# Text-to-Cypher baselines

Test set: `data/test.jsonl`, 200 rows, sha256 in `data/TEST_HASH`. 40 rows per graph (movies, recommendations, northwind, fincen, twitter), executed live on `neo4j+s://demo.neo4jlabs.com`.
Prompt: `prompts/v1_plain.txt` (the graph's schema text, then "Return only the Cypher query"). Temperature 0, max_tokens 4096, default reasoning except nemotron (`reasoning_effort: "none"`). One seed.
Sanity check: re-executing the gold queries scores 200/200 (`results/gold_v1_plain_n200.json`), so the server is deterministic for this set.

**Strict** = the predicted result set equals the gold result set as an unordered multiset of rows (column names and column order ignored, floats to 3 dp).
**Lenient** = strict, plus a row counts when the prediction returns extra columns, or returns properties where gold returned whole nodes. Row counts must still match. Strict is the headline number; lenient shows how much of the gap is projection style rather than wrong logic.
error = query failed to run (syntax, unknown function, timeout) or no query returned; empty = ran but returned no rows; wrong = rows differ.

| model | config | n | accuracy (strict) | accuracy (lenient) | wrong | error | empty | p50 s | p95 s | $/1k | out tok/row | reasoning tok/row |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| glm-5p3 | v1_plain | 100 | 60.0% | 80.0% | 38.0% | 1.0% | 1.0% | 2.30 | 7.89 | $2.571 | 322 | 277 |
| kimi-k3 | v1_plain | 100 | 58.0% | 74.0% | 41.0% | 0.0% | 1.0% | 3.26 | 6.67 | $5.462 | 198 | 143 |
| glm-5p3-flash | v1_plain | 200 | 54.5% | 69.0% | 44.5% | 0.5% | 0.5% | 1.38 | 3.70 | $0.228 | 203 | 159 |
| deepseek-v4p1-flash | v1_plain | 200 | 52.0% | 68.5% | 45.5% | 1.5% | 1.0% | 2.02 | 10.46 | $0.802 | 446 | 397 |

**Accuracy by graph**

| model | n | movies | recommendations | northwind | fincen | twitter |
|---|---|---|---|---|---|---|
| glm-5p3 | 100 | 76% (25) | 62% (21) | 72% (18) | 52% (21) | 27% (15) |
| kimi-k3 | 100 | 80% (25) | 67% (21) | 61% (18) | 48% (21) | 20% (15) |
| glm-5p3-flash | 200 | 60% (40) | 68% (40) | 40% (40) | 65% (40) | 40% (40) |
| deepseek-v4p1-flash | 200 | 60% (40) | 52% (40) | 42% (40) | 68% (40) | 38% (40) |

**Accuracy by complexity tier** (easy: 0 to 1 hop, no aggregation; medium: multi-hop or aggregation; hard: both)

| model | easy | medium | hard |
|---|---|---|---|
| glm-5p3 | 50% (32) | 67% (51) | 59% (17) |
| kimi-k3 | 50% (32) | 65% (51) | 53% (17) |
| glm-5p3-flash | 46% (70) | 65% (86) | 48% (44) |
| deepseek-v4p1-flash | 49% (70) | 58% (86) | 45% (44) |

**Apples to apples: all models on the same first 100 test rows**

| model | strict (first 100) | lenient (first 100) |
|---|---|---|
| glm-5p3 | 60% | 80% |
| kimi-k3 | 58% | 74% |
| glm-5p3-flash | 63% | 74% |
| deepseek-v4p1-flash | 57% | 73% |

On the first 100 rows, 24 rows are missed by every model; 76 are solved by at least one model (oracle ceiling).

Ledger total: $1.0424

## Reading the numbers
- Most misses are "wrong", not "error": models write valid Cypher that answers a slightly different question (extra or missing columns, returning a node instead of a name, a different interpretation of "top"). Execution errors are 0 to 2%.
- 11 test rows use LIMIT without ORDER BY, so the gold rows are arbitrary ("list 3 movies..."). A correct query can return different rows. Accuracy on the other 189 rows moves by under 1 point, so this does not change the ranking.
- glm-5p3 and kimi-k3 were run on the first 100 rows only (cost); use the "same first 100 rows" table for model-to-model comparisons.

Regenerate: `sh scripts/write_baselines.sh`
