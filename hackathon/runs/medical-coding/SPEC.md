# SPEC: clinical note → ICD-10-CM category codes

**Task (one line):** Given a short synthetic clinical note (80-150 words), output the set of ICD-10-CM category codes (3-character, e.g. `E11`, `I10`) that the note supports, restricted to a fixed list of 60 common categories.

**Input:** note text, plus the 60-code list (code + description) given to the model in the prompt.
**Output:** a JSON array of codes, e.g. `["E11","I10"]`. 1 to 4 codes per note.

**Scoring (`score.py`):**
- Primary: set-level F1 between predicted and gold code sets, averaged over notes (per-note F1, then mean). Reported as "accuracy" in the results table so the judge's parser works; it is F1.
- Secondary: exact-set accuracy (predicted set == gold set).
- A predicted code not in the 60-code list is dropped before scoring and the output is counted as "invalid" if the output cannot be parsed at all or contains zero in-list codes.
- Temperature 0; max_tokens high enough for reasoning models (hidden thinking tokens are handled).

**Data:** synthetic. Labels are sampled FIRST from the 60-code list with a seeded RNG (1-4 codes, weights .25/.35/.25/.15), then glm-5p3 writes a note that implies exactly those conditions. The labels therefore come from the sampler, not from a model's opinion. No real patient data anywhere. 500 notes; 180 locked as `data/test.jsonl`, 320 as `data/train.jsonl`.

**Who pays:** outpatient coding teams at clinics, revenue-cycle vendors, and billing companies. Medical coders cost roughly $25-35/hour and code about 20-40 outpatient encounters per hour; a model that pre-codes notes for human review cuts the time per chart, and each missed/incorrect code is a denied or under-paid claim.

**Workload assumption (for BUSINESS.md):** a mid-size revenue-cycle vendor processing 50,000 outpatient encounters per day.
