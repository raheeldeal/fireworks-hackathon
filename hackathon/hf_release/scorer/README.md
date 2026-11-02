# Scorer

Three files, copied unchanged from the project:

| file | what it does |
|---|---|
| `executor.py` | Runs a Cypher query read-only against the public Neo4j Labs demo server (`neo4j+s://demo.neo4jlabs.com`, user = password = graph name). Returns rows, columns, and any error. 10 s timeout, 1000-row cap. |
| `score.py` | Compares a predicted result with the gold result. `score_v2` is the scorer used for every number in the dataset card. `score` (v1, strict) and `score_lenient` are kept so old numbers can be reproduced. |
| `test_score.py` | 31 unit tests that pin the rules below. They need no network. |

## How grading works, in plain English

This is **execution accuracy**: run both queries on the same graph and compare what comes back. Two different Cypher strings that return the same answer both count. This is the standard used by Spider, BIRD, and Neo4j's own Text2Cypher work.

`score_v2` rules:

1. **Row order does not matter, duplicates do.** Rows are compared as a bag. `RETURN x` and `RETURN DISTINCT x` can differ, and that difference counts.
2. **Column names do not matter.** `AS actor` and `AS name` are the same answer.
3. **Column order does not matter.**
4. **One-column rows are unwrapped** to plain values, so they compare cleanly with lists.
5. **Numbers:** floats are rounded to 3 decimals, and `2` equals `2.0`.
6. **Lists are unordered**, and one row holding a list of N values equals N rows of one value each (`collect(x)` vs one row per `x`).
7. **Node vs its name.** If one side returns a whole node (`RETURN m`) and the other returns its identifying property (`RETURN m.title`), both are reduced to that identifier (`name`, then `title`, then `id`, then a `<label>Id` key). Returning a different property such as `m.year` still fails.
8. **`LIMIT` with no `ORDER BY`.** The database picks which rows come back, so any prediction with the right number of rows that the gold query could also have returned (checked by re-running gold without its `LIMIT`) counts. 17 of the 200 test rows are in this state.
9. **Ties at a `LIMIT` cut.** If gold sorts then cuts, and several rows tie at the cut, a prediction that picks a different set of tied rows counts, but only if its sort-key values match gold's exactly. Not applied when any gold sort key is `null`.
10. **Errors and empty results are wrong.** They are tracked separately for diagnosis.
11. **Empty gold** is matched only by an empty prediction.

What v2 deliberately does **not** forgive:

- **Extra or missing columns.** A prediction that returns the right rows plus a column the question did not ask for is wrong. So is one that drops a column gold has. This is the single biggest source of disagreement on this test set, and it is a dataset problem (many gold queries project columns their question never asked for), not a scorer rule. See the dataset card.
- **Ambiguous questions.** No allowance. Each rule above would have to be accepted if our own model were the one losing.

Every rule is symmetric between gold and prediction.

## Known gold defects

`t020`, `t047`, `t083`, `t138` read properties or edges the graph does not have, so gold returns 0 or null and any equally broken prediction would score correct. Report accuracy on the remaining 196 rows as well as all 200.

## Run the tests

```
pip install pytest
cd scorer
python -m pytest -q test_score.py      # expect: 31 passed
```

## Score a prediction yourself

```
pip install neo4j
```

```python
from executor import execute
from score import score_v2, strip_limit
gold = execute(row["graph"], row["cypher"])
pred = execute(row["graph"], predicted_cypher)
gold_unlimited = execute(row["graph"], strip_limit(row["cypher"]))  # only needed for LIMIT rows
print(score_v2(gold, pred, row["cypher"], gold_unlimited))         # correct | wrong | error | empty
```

The gold Cypher stores line breaks as the two characters `\` `n`. `execute()` converts them to real line breaks before running; the stored text is never changed.

The demo server is a public, shared Neo4j Labs service. If it is down or its data changes, live results will drift from the stored `gold_result`.
