# Harness status

Updated 11:40 PT.

## Built (code in `harness.py`, runner `run_harness.py --config <name>`)
1. **validate(query, schema)**: rejects writes (CREATE, MERGE, DELETE, SET, REMOVE, DROP, LOAD CSV, FOREACH), admin procedure calls and multiple statements; checks every node label, relationship type, property (on variables bound to a label) and simple relationship direction against the schema text. Reads both schema formats in the dataset (bulleted and compact `Label {prop: TYPE}`).
   - Check on gold queries: 196 of 200 test golds pass. The 4 it flags (t020, t047, t083, t138) are real gold defects: they use properties that do not exist (for example `Order.discount`) and return 0 or null. Those 4 rows reward a wrong query.
2. **generate_and_repair**: one call, validate, execute; on error, empty result or schema problems, one repair call with the problem text, then re-execute. Keeps the repair only if it is not worse (rows beats empty beats error).
3. **vote3**: three repair chains at temperature 0.7 in parallel; majority by result set using score.py's multiset comparison; records agreement 3, 2 or 1 (none).
4. **route**: vote3, then glm-5p3 when no two agree.
5. **schema_prune**: keeps schema parts whose word stems appear in the question, plus relationship endpoints; full schema if fewer than 2 labels survive. Offline check: shrinks the schema text about 18% on average, falls back on 42 of 200 rows, and drops something the gold query needs on 6 rows. Repair always sees the full schema.
6. **retrieve_examples**: 2 training rows from the same graph by word overlap, used in the `repair1_fewshot` retry message.

Small model: glm-5p3-flash with `reasoning_effort: low` (`none` is rejected by the API: "thinking-only model").

## Results so far (200 rows, glm-5p3-flash, reasoning low)
- **Plain (no harness), reasoning low: 48.0%.** This is 6.5 to 9 points below the BASELINES.md flash run (54.5% to 57%) that used the model's default reasoning. Turning reasoning down costs accuracy; a `repair1` run at default reasoning is going now to measure that cleanly.
- **validate_only: 48.0%, 3.0% invalid.** The validator rejected 6 queries total across error and gate; the 3 it gated were all wrong anyway (2 empty, 1 wrong), so it cost zero correct answers. It does not raise accuracy by itself; it stops bad queries before they run.
- **repair1: 50.0% (+2.0 points), error 0.5%, empty 1.0%, 1.05 calls per row, $0.157 per 1k.** Repair only fires on 5% of rows because the model rarely writes broken Cypher; most misses are queries that run and return the wrong rows, which repair cannot see.

- **repair1 at default reasoning: 53.0%**, $0.252 per 1k. Reasoning low vs default is worth 3 points at this stage.
- **vote3: 52.0%**, 3.2 calls per row, $0.474 per 1k. Agreement: 140 rows 3/3, 46 rows 2/3, 14 rows none. Accuracy by agreement 58.6% / 39.1% / 28.6%. If any of the three chains is correct the ceiling is 112/200 (56%).
- **route_big: 55.0%**, escalated 6% of rows to glm-5p3, $0.771 per 1k. Part of the gap to vote3 is run-to-run noise in the small-model vote (its own vote here had 147 unanimous rows).
- **prune_repair1: 47.5%** (minus 2.5 vs repair1), empty rate up to 2.5%. Pruning hides schema parts the model needs.
- Unanimous-but-wrong rows (58 in vote3): 19 of them are correct under the lenient metric (extra columns, whole node vs properties), the rest are mostly ties under LIMIT and alternative readings of the question. Much of the remaining gap is gold ambiguity, not model failure.

## Running now
Extra: route_big_u (escalate unless 3/3 agree), vote3 and route_big_u at default reasoning. Then repair1_fewshot.

## Old note
All six configs in order (validate_only, repair1, vote3, route_big, prune_repair1, repair1_fewshot) via `run_all.sh`. Smoke test spend so far: under $0.01.
