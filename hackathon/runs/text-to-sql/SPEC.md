# Text-to-SQL (Spider) — task spec

**One line:** given a natural-language question and a compact database schema, write one SQLite `SELECT` query that answers it.

**Input → output**
- Input: `schema` (one line per table: `table(col type [PK] [FK->table.col], ...)`, 66 to 519 tokens on the test set) + `question`.
- Output: a single SQL statement, nothing else.

**Scoring (score.py, deterministic)**
- Primary: **execution accuracy**. Gold and predicted SQL run read-only on the same Spider SQLite database with a 5 s timeout; result sets are compared as unordered multisets of rows (ordered comparison when the gold has ORDER BY).
- Secondary: exact match after whitespace/case/quote normalization.
- Guardrail: output is normalized (code fences, prose prefix, `</think>` leakage stripped; first statement only). Anything that is not a single SELECT/WITH, fails to execute or times out scores 0 and counts as **invalid**.

**Data:** Spider 1.0 (Yu et al., 2018, CC-BY-SA-4.0). Test = 180 rows from the dev split across all 20 dev databases (round-robin, seed 20261101, gold must execute). Train = 450 rows from the train split (121 databases, disjoint from dev by Spider's construction, ≤ 6 per DB, schema ≤ 450 tokens).

**Who pays:** analytics / BI vendors and internal data teams that let non-technical staff ask questions of a warehouse in plain English (self-serve analytics, "chat with your data"). A wrong query that *runs* is the expensive failure: it returns a plausible wrong number.

**Workload assumption for BUSINESS.md:** 50,000 questions/day for a mid-size SaaS analytics product (about 2,000 business users × 25 questions). Each wrong answer costs an analyst ~10 minutes to catch and redo.
