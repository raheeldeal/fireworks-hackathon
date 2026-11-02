# Task spec: natural language → Python regex

**One line.** Given an English description of a set of text lines, output a Python regular expression that accepts exactly those lines.

**Input → output.** Input: one English sentence such as `lines that contain words starting with 'pa'.` Output: one Python `re` pattern such as `.*\bpa[A-Za-z]*\b.*`. The pattern is applied with `re.fullmatch` to whole lines.

**Scoring rule (execution-based, deterministic).** Each test row carries 10 positive strings (generated from the gold regex with `exrex`, kept only if the gold regex full-matches them) and 10 negative strings (mutations of positives that the gold regex rejects). A prediction is **correct** only if it full-matches all 10 positives and rejects all 10 negatives. **Soft score** = fraction of the 20 strings handled correctly. A prediction that does not compile, or that cannot be extracted from the model output, is **invalid** (counts as wrong, soft 0). Each match runs with a 1-second timeout in a forked process; a timeout counts as a wrong string. See `score.py` (`python3 score.py --test` runs 9 unit cases including a wrong answer that must score 0, a compile error, and a catastrophic-backtracking pattern).

**Why strings and not string equality of regexes.** Two different patterns can accept the same language (`.*\bthe\b.*` vs `(.*\s|)the(\s.*|)`), and the gold regexes in this dataset are in a 2013/2016 dialect. Testing behaviour on strings is the only fair comparison.

**Data.** KB13 and NL-RX-Synth from `nicholaslocascio/deep-regex` (MIT). Test = 200 KB13 rows (human-written descriptions, one row per unique gold regex). Train = remaining KB13 rows plus NL-RX-Synth rows. Rows whose gold uses the paper's DSL-only operators `&` and `~` were dropped (not executable by Python). Details in `DECISIONS.md`.

**Who pays for it.** Teams that ship log-search, data-validation, ETL and data-quality tooling (Datadog/Splunk-style query builders, form validators, Airbyte/dbt pipelines, spreadsheet "extract pattern" features). Each regex an analyst or support engineer writes by hand costs 5 to 15 minutes and is a top source of validation bugs; an "describe it in English" feature inside the product is the demand.

**Workload assumption for the business model.** 50,000 regex requests per day (one mid-size observability or data-tooling product's "pattern from description" feature). Every wrong regex is either a silent data-quality bug or a support ticket; we price an error at 10 minutes of engineer time ($15).

**Why this task is interesting for small vs. frontier.** Regex is a narrow formal language with a checkable answer: exactly the shape where LoRA Land, Think2SQL and the Vercel v0 results showed small tuned models matching frontier. Frontier models also stumble on word-boundary semantics and "at least N" counting, so there is headroom to show.
