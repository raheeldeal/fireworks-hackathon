# SPEC: Product listing text → strict JSON

**Task (one line):** Given a messy e-commerce product listing (title + blurb, as a seller would paste it), return one JSON object with exactly eight fields describing the product.

**Input:** a single string, 40 to 220 words, with real-world noise: ALL CAPS, emojis, SEO keyword stuffing, strike-through "was/now" prices, shipping costs, "also available in …" colour distractors, size ranges vs. the size actually sold, pack counts spelled out in words, brand names in odd places or with ® / ™.

**Output:** JSON matching `schema.json`:

| field | type | rule |
|---|---|---|
| brand | string | the seller brand as written in the listing (case-insensitive match) |
| product_type | enum (24 values) | what the item is; closed list so exact match is fair |
| color | enum (16 values) or null | the colour of the item being sold, not alternatives offered |
| size | string or null | the size actually sold (e.g. "M", "10", "Queen", "One Size"); null if none stated |
| material | enum (15 values) or null | primary material; null if none stated |
| price_usd | number or null | the price the buyer pays now (sale price beats list price; ignore shipping and "save $X") |
| quantity | integer ≥ 1 | number of identical units in the listing (pack of 3 → 3); 1 if not stated |
| is_bundle | boolean | true only if the listing sells two or more *different* item types together (kit / set with accessories) |

**Scoring (score.py):** output must parse as JSON and validate against the schema (correct keys, types, enums); otherwise the row is *invalid* and scores 0 on every field. Then each field is compared after normalisation (lowercase, strip, collapse whitespace, strip "®™", prices rounded to cents, sizes upper-cased with spaces removed). Reported metrics: per-field accuracy (8 numbers), mean field accuracy, and **all-fields-correct accuracy** (the headline number; one wrong field = wrong row), plus invalid rate.

**Data:** synthetic path (see DECISIONS.md): gold attribute values are *sampled* (brands drawn from real Amazon ESCI brand strings, everything else from the enum lists), then `glm-5p3` writes a messy listing that embeds them. A regex check confirms each gold value is literally present in the text before a row is kept, so the gold is not a model opinion.

**Who pays:** marketplace / catalogue teams (Shopify apps, Amazon aggregators, price-comparison engines, retail media) that ingest millions of seller-written listings and need clean attributes for search filters, ads and pricing. A wrong attribute is a lost filter match or a mispriced item; an invalid JSON is a pipeline exception a human handles.

**Workload assumption for BUSINESS.md:** 500,000 listings per day (a mid-size aggregator re-crawling its catalogue), ~450 input tokens and ~90 output tokens each.
