# SPEC: legal clause classification (LEDGAR, 100 classes)

**Task in one line:** given one contract clause (plain text, under ~400 tokens), output its provision category from a fixed list of 100 LEDGAR labels.

**Input → output:** `text` (clause) → one label string, exactly as it appears in `data/labels.json` (e.g. `Governing Laws`). The model is given the full list of 100 labels, each with a one-line definition we wrote.

**Scoring rule:** exact label match after light normalization (case, whitespace, trailing punctuation, stripped quotes/backticks, `</think>` leakage removed). Primary metric accuracy; secondary macro-F1 over the 100 classes. An output that normalizes to nothing in the label set counts as `invalid` and is scored 0 (reported separately).

**Data:** LEDGAR via Hugging Face `coastalcph/lex_glue`, config `ledgar` (Tuggener et al. 2020, CC-BY-4.0; SEC EDGAR contracts). Test: 2 clauses per class from the official test split (199 rows; `Books` has only 1 eligible clause). Train: 3 per class from the official train split (300 rows). Clause length 20 to 250 words (word-count proxy for the 400-token limit).

**Who pays:** contract lifecycle management (CLM) vendors and legal-ops teams (Ironclad, DocuSign CLM, in-house legal at banks) who tag clauses to build searchable clause libraries, run playbook compliance, and flag missing or non-standard provisions. Today this is done by paralegals or by brittle keyword rules.

**Workload assumption:** a mid-size CLM customer processes 2,000 contracts/day x 60 clauses = 120,000 clause classifications/day (3.6M/month). See BUSINESS.md.
