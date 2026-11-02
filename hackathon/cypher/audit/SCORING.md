# `score_v2`: what counts as correct, and why

This is the scoring standard for the text-to-Cypher eval, implemented as `score_v2` in `score.py`.
`score` (v1, strict) and `score_lenient` are kept unchanged so all three can be run over the same
stored predictions and compared.

## The standard we are adopting

**Execution accuracy with result-set equality.** The predicted query is run against the same
database as the gold query; the prediction is correct when the two result sets are equal as
*sets/multisets of rows*, independent of column names, column order, and row order unless the
question pins the order. This is the standard metric in the published text-to-SQL and
text-to-Cypher literature, not something invented here:

- **Spider** (Yu et al., EMNLP 2018) reports *execution accuracy* alongside exact-set-match, and the
  **Spider test-suite** evaluation (Zhong, Yu & Klein, EMNLP 2020) defines correctness as denotation
  equality of the returned relations rather than string equality of the query.
- **BIRD** (Li et al., NeurIPS 2023) uses execution accuracy as its headline metric: a prediction
  counts when its result set equals the gold result set, with row order ignored unless the gold
  query has `ORDER BY`.
- **Neo4j's Text2Cypher work** (Ozsoy et al., 2024, the `neo4j/text2cypher-*` datasets this test set
  is drawn from) evaluates by running the generated Cypher on the live demo graphs and comparing
  returned results, precisely because two different Cypher strings routinely return the same answer.

Two deliberate consequences of adopting a published standard rather than writing our own:

1. **We did not adopt `score_lenient`'s extra-column rule.** `score_lenient` passes a prediction
   whose row values are a *superset* of gold's. No published execution-accuracy metric does that,
   and a judge would reject it: returning columns the question did not ask for is a different
   result set. v2 therefore scores lower than the ~65% lenient number.
2. **We did not add any "ambiguous question" allowance.** The audit found genuinely ambiguous rows,
   but "both readings are defensible" is a dataset problem, not a scoring rule. Encoding it would
   let a prediction pass by answering a question we made up after seeing its output.

Every rule below is symmetric: it would have to be accepted if our model were the loser.

## The rules

| # | Rule | One-line justification |
|---|---|---|
| R1 | Rows are compared as **multisets**: row order is ignored, but duplicate rows must match in count. | Cypher's output order is unspecified without `ORDER BY`; duplicate counts are real information (they distinguish `RETURN x` from `RETURN DISTINCT x`), so we keep them. |
| R2 | **Column names are ignored.** | Aliases are free text (`AS actor` vs `AS name`); the question never specifies them, so penalising them measures nothing. |
| R3 | **Column order is ignored** (a row's values are compared as an unordered tuple). | `RETURN a.name, c` and `RETURN c, a.name` are the same answer; no question in the set asks for a particular column order. |
| R4 | **Single-column rows are unwrapped** to their scalar value. | Removes the 1-tuple wrapper so a one-column result compares cleanly against the list form in R6. |
| R5 | Numbers: **floats rounded to 3 dp**, and `2 == 2.0`. | `toFloat()`/`avg()` vs integer division differ in the 15th decimal; the answer to "what is the average" does not. 3 dp still separates genuinely different values. |
| R6 | **Lists are compared unordered**, and one row holding `collect(x)` of N values is equal to N single-column rows of `x`. | `collect()` order is unspecified in Cypher, and "list the genres" is answered equally by one list or one row per genre. |
| R7 | When one side returns a **node or relationship object** and the other returns a scalar property, both are reduced to the node's **identifying property** (`name`, then `title`, then `id`, then a `<label>Id` key) and compared on that. | `RETURN m` and `RETURN m.title` name the same set of movies; which of the two the gold author picked is a style choice. Reduction only applies to node/relationship objects, so returning a *different* property (`m.year`) still fails. |
| R8 | **`LIMIT` without `ORDER BY`:** accept any prediction with the same number of rows as gold whose rows are all contained (as a sub-multiset) in the gold query's own result with every `LIMIT`/`SKIP` removed (re-executed once, 10 s cap). | With no `ORDER BY`, *which* rows the gold query returns is chosen by the query planner, not by the question. The accepted sets are exactly the sets the gold query itself may return on another execution, so grading against one of them is grading a coin flip. 17 of the 200 rows are in this state. |
| R9 | **`LIMIT` with `ORDER BY`, ties at the cut:** accept a same-size prediction contained in the unlimited gold result **only if its multiset of `ORDER BY` key values equals gold's**. If the `ORDER BY` expression cannot be resolved to a returned column (e.g. `ORDER BY rand()`), no relaxation is applied. | Same non-determinism, narrowly scoped: with 4 actors tied on 17 genres and `LIMIT 3`, the gold query returns a different 3 depending on the plan. Requiring the key multiset to match means a prediction returning the *bottom* k, or a different number of ties, still fails - it must be a legitimate top-k. |
| R10 | A prediction that **errors** scores `error`; one that returns **no rows while gold has rows** scores `empty`. Both count as incorrect. | They are failures, tracked separately only for diagnosis. |
| R11 | Gold returning **no rows** is matched only by a prediction returning no rows. | Keeps the vacuous case honest instead of passing anything. |

## What v2 does **not** do (and we checked)

- No extra/missing column tolerance (R-not-adopted, above).
- No subset/superset tolerance on ordinary queries: `test_v2_limit_rule_does_not_rescue_a_wrong_query`
  pins that the R8/R9 containment test only fires when the gold query actually has a `LIMIT`.
- No tolerance for a wrong aggregate value, a different entity, a wrong property, or an empty
  result where gold has rows. `test_v2_must_still_be_wrong` and
  `test_v2_node_vs_identifying_property` pin each of these.

## Known gold defects, excluded rather than scored

`t020`, `t047`, `t083`, `t138` have gold queries that read properties the graph does not have
(`Order.discount`, `Filing.originator_country`, ...), so gold is `0` or `null`. Any prediction that
also returns 0/null scores correct on them, which rewards a broken query. We cannot edit
`data/test.jsonl`, so `results_v2/*.json` carries both `accuracy_v2` (all 200 rows) and
`accuracy_v2_excl_gold_defects` (196 rows). **Quote the 196-row number.** This cuts our headline,
which is the point: it is the number a judge would hold us to.

## The 78% comparison

Published text-to-Cypher numbers near 78% are measured on *different test sets* with *different
scorers*; they cannot be used to calibrate this one, and "our number is below theirs" is not
evidence that our scorer is wrong. The reason to change the scorer is R1-R11 above, each of which
is defensible on its own. The hand audit in `MISS_AUDIT.md` is the evidence that the old scorer was
mis-grading; the 78% figure is not.
