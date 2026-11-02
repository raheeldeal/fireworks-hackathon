---
license: apache-2.0
language:
- en
task_categories:
- text-generation
- table-question-answering
tags:
- text2cypher
- cypher
- neo4j
- graph-database
- knowledge-graph
- code
- evaluation
- benchmark
pretty_name: Text2Cypher Executed 200
size_categories:
- n<1K
source_datasets:
- neo4j/text2cypher-2025v1
configs:
- config_name: default
  data_files:
  - split: test
    path: data/test.parquet
  - split: train
    path: data/train.parquet
- config_name: test_annotations
  data_files:
  - split: test
    path: data/test_annotations.parquet
---

# Text2Cypher Executed 200

A small, **execution-verified** text-to-Cypher benchmark: 200 locked test questions and 500 training questions drawn from [`neo4j/text2cypher-2025v1`](https://huggingface.co/datasets/neo4j/text2cypher-2025v1), each tied to one of five public Neo4j demo graphs, with every gold query actually run and its result stored. It ships with a hand audit of where the gold answers are wrong, a per-row annotation file, and the scorer used to grade it.

It was built during a one-day hackathon to compare open models, fine-tuning, and an agent harness on natural-language-to-Cypher. The most useful thing it turned out to contain is evidence about the source benchmark itself: **many "model errors" on this data are errors in the gold answer.**

## At a glance

| | test | train |
|---|---|---|
| rows | 200 (locked) | 500 |
| source split | `text2cypher-2025v1` test | `text2cypher-2025v1` train |
| graphs | movies, recommendations, northwind, fincen, twitter (40 each) | same five (100 each) |
| tiers (easy / medium / hard) | 70 / 87 / 43 | 218 / 203 / 79 |
| stored gold result | yes (`gold_result`) | row count only (`gold_n_rows`) |

Test set sha256 (of `data/test.jsonl`):

```
6c47ee00573e7ebc4e144c7e31363b2f3c72b10556e5d2c853323cc85733b491
```

Zero overlap between splits: no test question or normalised gold Cypher appears in train (checked by script at build time).

## Files

| path | what it is |
|---|---|
| `data/test.jsonl` | The 200 locked test rows, byte-identical to the hashed file. |
| `data/train.jsonl` | 500 training rows. |
| `data/test.parquet`, `data/train.parquet` | Same rows for the Dataset Viewer. In parquet, `gold_result` is a JSON string (the rows hold mixed types that parquet cannot store as one struct). `json.loads` it to get the original object. |
| `data/test_annotations.jsonl` / `.parquet` | One row per test id: tier, complexity flags, live re-execution check, tie-at-cut flag, hand-audit class, and whether every model run missed it. The original rows are never modified. |
| `scorer/` | `executor.py`, `score.py`, `test_score.py` (31 tests) and a plain-English README of the scoring rules. |

### Row fields (test)

| field | meaning |
|---|---|
| `id` | `t000`-`t199` |
| `question` | natural-language question (from the source dataset) |
| `cypher` | gold Cypher (from the source; line breaks stored as the two characters `\n`, unchanged) |
| `schema` | graph schema text given to the model |
| `graph` | which demo database to run against |
| `gold_result` | `{"columns": [...], "rows": [...]}` from executing `cypher` |
| `gold_n_rows` | number of gold rows |
| `complexity` | `hops`, `multi_hop`, `aggregation`, `where`, `order_by`, `limit`, `var_length`, `tier` |
| `data_source` | the source dataset's own provenance tag (e.g. `neo4jLabs_synthetic_gpt4o`) |
| `source_dataset`, `source_split`, `source_id` | pointer back to the original row |

Train rows have the same fields minus `gold_result`.

### Annotation fields

| field | meaning |
|---|---|
| `tier`, `hops`, `multi_hop`, `aggregation`, `where`, `order_by`, `limit`, `var_length` | copied from `complexity` for easy filtering |
| `gold_executes` | gold query ran without error when re-executed for this release (200 / 200) |
| `gold_n_rows`, `gold_n_rows_live`, `gold_live_matches_stored` | stored vs live row count (200 / 200 match) |
| `tie_at_limit_cut` | gold has `ORDER BY` + `LIMIT k`, and with the `LIMIT` removed at least one row past position k has the same sort value as row k. So *which* k rows gold returns is arbitrary. `null` = not applicable or the sort key could not be resolved. Counts `null` sort values as ties. |
| `defect_class` | hand-audit verdict: `SCORING_ARTIFACT`, `GOLD_DEFECT`, `AMBIGUOUS_QUESTION`, `REAL_ERROR`, or `unaudited` |
| `defect_note` | one-line reason for the verdict |
| `audit_v2_verdict` | how the audited model's prediction scores under `score_v2` |
| `n_runs_scored`, `n_runs_correct` | over the 31 model/harness runs in the project (29-31 runs cover each row) |
| `models_missed_by_all` | `true` if every run that saw the row got it wrong |

## How it was built

1. Downloaded `neo4j/text2cypher-2025v1` and kept rows whose `database` is one of the five graphs hosted on the public Neo4j Labs demo server (`neo4j+s://demo.neo4jlabs.com`).
2. Executed every candidate gold query against its live graph (read-only). Kept only rows that ran without error, returned at least one row, were not truncated at 1000 rows, and finished in under 8 s.
3. Tagged each query's complexity from the Cypher text: **easy** = one hop, no aggregation; **medium** = multi-hop *or* aggregation; **hard** = both.
4. Sampled 40 test rows per graph (target 10 hard, 14 easy, the rest medium; movies has only 4 hard rows available) with a fixed seed, stored the executed result, and locked the file by sha256.
5. Sampled 100 train rows per graph from the source train split, excluding any question or gold Cypher that appears in test.
6. For this release, re-executed every test gold query: 200 / 200 still run and return the stored row count.

## Audit findings

### Hand audit of 40 scored-wrong rows

Model audited: `glm-5p3-flash`, the best small model. We took **all 36 easy-tier misses** plus the first 4 medium-tier misses, re-executed the predictions, and compared full row sets by hand.

| class | all 40 | of the 36 easy | meaning |
|---|---|---|---|
| SCORING_ARTIFACT | 20 | 19 | prediction is right; result differs only in projection (which columns), node vs name, or tie choice |
| GOLD_DEFECT | 11 | 9 | gold does not answer its own question (duplicates, all-`null` answers, wrong field) |
| AMBIGUOUS_QUESTION | 7 | 6 | two defensible readings ("first 3" with no order, date vs year) |
| REAL_ERROR | **2** | **2** | the model is actually wrong (both: forgot to filter `null` before sorting) |

**On easy-tier misses the model is genuinely wrong 2 times in 36.** The corrected scorer (`score_v2`) recovers only 5 of the 20 scoring artifacts. The other 15 are pure projection mismatches (same rows, different columns), which v2 deliberately does not forgive.

Separately, 4 more test rows (`t020`, `t047`, `t083`, `t138`) query properties or edge directions the graph does not have, so their gold answer is 0 or `null`. They are marked `GOLD_DEFECT` in the annotations (15 `GOLD_DEFECT` rows in total) and should be excluded when reporting a clean number (196 rows).

### Projection mismatch across the set

Roughly **30 of the 200 gold queries** project columns their own question does not ask for, or omit ones it does. On the audited run, 31 of 79 v2 misses return exactly gold's rows with different columns. This is why the "easy" tier scores *lowest* for every model: an easy question like "list the movies" leaves the gold author free to pick `RETURN m`, `RETURN m.title`, or `RETURN m.title, m.votes`.

### Ties at the LIMIT cut

113 test rows sort and then cut (`ORDER BY ... LIMIT k`). In **32** of them, rows past the cut tie with the last kept row, so the gold's top-k is one arbitrary pick among several (53 have no tie; 28 could not be resolved). Wrong answers on tied rows, per model:

| run | wrong | of which tie-at-cut | accuracy if those were forgiven |
|---|---|---|---|
| kimi-k3 (n=100) | 50 | 13 | 63.0% |
| glm-5p3 large (n=100) | 51 | 12 | 61.0% |
| deepseek-v4.1-flash | 94 | 20 | 63.0% |
| glm-5p3-flash | 79 | 12 | 66.5% |
| 30B + SFT | 82 | 12 | 65.0% |

This counts `null` sort values as ties. `score_v2` is stricter: it forgives a tie only when the prediction's sort-key values match gold's exactly and none is `null`.

### Questions nobody gets

- **39 of 200** test rows are missed by all 31 model and harness runs in the project.
- On the first 100 rows, where all four off-the-shelf models were run, **34** are missed by every one of them under `score_v2` (glm-5p3-flash, kimi-k3, glm-5p3, deepseek-v4.1-flash). Of the 39, 21 were in the hand audit: 8 scoring artifacts, 6 gold defects, 5 ambiguous, 2 real errors.

## Leaderboard

Strict execution accuracy under `score_v2`, all 200 rows unless noted. Same 100 rows for the n=100 entries.

| setup | accuracy | cost / 1k questions | n |
|---|---|---|---|
| kimi-k3 | 50.0% | $6.36 | 100 |
| glm-5p3 (large) | 49.0% | $3.13 | 100 |
| deepseek-v4.1-flash | 53.0% | $0.82 | 200 |
| **glm-5p3-flash (small, off the shelf)** | **60.5%** | **$0.24** | 200 |
| Muse Glimmer 30B, untuned | 51.5% | $1.89* | 200 |
| Muse Glimmer 30B + SFT on `train` | 59.0% | $1.89* | 200 |
| Muse Glimmer 30B + SFT + RFT (rejection sampling) | 60.0% | $1.86* | 200 |
| small model + harness with routing | 59.0% | $0.77 | 200 |

\* measured through a training-API sampler; normal serving would be about $0.25 / 1k.

With extra output columns tolerated (the prediction must still contain gold's columns): kimi-k3 55.0%, glm-5p3-flash 66.0%, SFT+RFT 64.0%, harness+routing 67.0%. The ranking does not change.

## Limitations

- **Five graphs only.** Train and test share the same five schemas. Scores here say nothing about generalising to an unseen graph.
- **LLM-generated source questions.** Most rows come from the source dataset's synthetic pipelines (`data_source`: gpt4o 61, gemini 58, gpt4turbo 43, claudeopus 29, crowdsourced 9 in test). The audit above shows what that costs: duplicates, `null` answers, and projections that do not match the question. *Mind the Query* (Chauhan et al., EMNLP 2025 Industry) independently notes that the Neo4j Text2Cypher data is LLM-generated without manual validation.
- **Depends on a public demo server.** Gold results were executed on `demo.neo4jlabs.com`, a shared service Neo4j Labs runs. If it changes data, versions, or goes offline, live re-execution will drift from the stored `gold_result`. Score against the stored result where you can.
- **Audit is partial.** 44 of 200 rows were hand-classified (40 from one model's misses, 4 known gold defects). The other 156 are `unaudited`, not "clean".
- **Small.** 200 test rows means about ±7 points at 95% confidence on a 60% score. Differences of 1-2 points between runs are noise.
- **Tier labels are mechanical.** They come from regexes over the Cypher, not human judgment of difficulty.

## License

Released under **Apache-2.0**, matching the source dataset `neo4j/text2cypher-2025v1`. Questions, Cypher, and schemas are from that dataset; executed results, annotations, and the scorer are new.

## Citation

Source dataset:

```bibtex
@misc{ozsoy2024text2cypher,
  title  = {Text2Cypher: Bridging Natural Language and Graph Databases},
  author = {Ozsoy, Makbule Gulcin and Messallem, Leila and Besga, Jon and Minneci, Gianandrea},
  year   = {2024},
  eprint = {2412.10064},
  archivePrefix = {arXiv}
}
```

Independent critique of the source data:

```bibtex
@inproceedings{chauhan-etal-2025-mind,
  title     = {Mind the Query: A Benchmark Dataset towards Text2Cypher Task},
  author    = {Chauhan, Vashu and Raj, Shobhit and Mujumdar, Shashank and Saha, Avirup and Jain, Anannay},
  booktitle = {Proceedings of the 2025 Conference on Empirical Methods in Natural Language Processing: Industry Track},
  year      = {2025},
  pages     = {1890--1905},
  url       = {https://aclanthology.org/2025.emnlp-industry.133}
}
```

## Contributing corrections

`data/test.jsonl` is frozen by its hash so results stay comparable. Corrections go in the annotations, not the rows.

1. Open a **Discussion** (or Pull Request) on this dataset page titled with the row id, e.g. `t050: gold orders by followers, question asks for most recent`.
2. Include: the question, the gold Cypher, what it returns, what a correct query returns (paste both result sets), and the class you propose (`GOLD_DEFECT`, `AMBIGUOUS_QUESTION`, `SCORING_ARTIFACT`).
3. Accepted corrections update `data/test_annotations.*`. If enough gold queries need fixing, they will ship as a separate, newly hashed `test_v2` file, never as an edit to this one.
