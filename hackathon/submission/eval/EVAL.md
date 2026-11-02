# Evaluation pack: tool routing (100-tool catalog)

Everything in this folder is derived from the locked test set and last night's per-row result files, offline,
except `adversarial.jsonl` (30 generator calls, $0.02). Nothing here modifies `../data/test.jsonl`.

## The test set

| | |
|---|---|
| Task | user request (one message) → the single best tool name from a 100-tool, 16-server catalog (`../data/catalog.json`) |
| File | `../data/test.jsonl`, 180 rows, one row per line: `{id, text, label, style}` |
| sha256 | `bb50067286893483a60bacd1d86b1a7f33ff5df7b809acb545dd85b085bcaf18` (`shasum -a 256 ../data/test.jsonl`) |
| Coverage | all 100 tools appear as gold; 16 servers; 5 request styles (terse, rambling, non-native, indirect, intercepted colleague message) |
| Label method | **gold-first synthetic**: the gold tool was sampled first, then `glm-5p3` was asked to write a request that needs exactly that tool and none of its same-server siblings (prompt: `../../runs/mcp-tool-pick/gen_data.py`). The label is never model-chosen, so no evaluated model's bias is baked into the gold. The generator (glm-5p3, large tier) is a different model from the small models we optimise and deploy. |
| Provenance | written 2026-11-01 by the overnight run in `../../runs/mcp-tool-pick/`, locked before any model was scored (`RESULTS.md` there records the hash); 320 training rows were generated the same way and split off before locking |
| Scoring | `../score.py`: top-1 exact match on the catalog name after normalisation (case, whitespace, punctuation, JSON/markdown wrappers, `<think>` blocks stripped). An output with no catalog name, or a name outside the catalog, is **invalid** and counts as wrong. |

Leak check of every file that is not the test set against the test set (`python3 ../../runs/common/check_leak.py`):

```
test set: 180 rows, sha256 bb50067286893483
../data/train.jsonl: 320 rows, 0 overlap with test
../data/train_sft.jsonl: 320 rows, 0 overlap with test
adversarial.jsonl: 30 rows, 0 overlap with test
```

## Scorer tests

`python3 -m pytest test_score.py -v` (11 cases, run 2026-11-02, all pass, no change to `score.py` was needed):

```
test_exact_match PASSED
test_case_and_whitespace_variance PASSED
test_wrong_tool_scores_zero PASSED
test_unknown_tool_name_is_invalid PASSED          gmail.send_mail (not in catalog) -> invalid
test_empty_and_none_output_are_invalid PASSED     "", None, "   "
test_json_wrapped_answer PASSED                   ```json {"tool": "calendar.create_event", ...}```
test_prose_without_catalog_name_is_invalid PASSED
test_think_block_is_ignored PASSED
test_ranked_list_top3_but_not_top1 PASSED
test_duplicates_deduped_and_order_kept PASSED
test_custom_catalog_argument PASSED
11 passed in 0.01s
```

`score.py` also carries 9 inline cases (`python3 ../score.py --test`).

## Hard slice and human labels (`hard_slice.jsonl`, `labeling_sheet.csv`, `agreement.py`)

Why: a synthetic label can be wrong or genuinely ambiguous. If two careful humans cannot agree on a row, no model
should be penalised for it. The hard slice finds those rows so we can state a ceiling instead of pretending 100% is reachable.

How it was built (`build_slices.py`, deterministic, seed 7, no API calls):

1. Take the 28 real model runs in `../../runs/mcp-tool-pick/results/` (the `route__*` files are offline recombinations of two of those runs and add no new predictions, so they are skipped).
2. A run is **strong** if its accuracy is at least 90%: 14 runs (deepseek-v4p1-flash, 10 glm-5p3-flash configs, glm-5p3, gpt-oss-120b, kimi-k3 on 100 rows).
3. Every row that **any** strong run got wrong goes on the slice: **21 rows**. Plus **10 control rows** that every strong run got right, sampled at random. 31 rows, shuffled. (No row survives all 28 runs because one nemotron ranked-list run scored 6% with 169 invalid outputs, so "all strong runs" is the control criterion.)
4. `candidate_tools` for each row = the gold tool plus every tool a strong run predicted for it, padded with same-server siblings to at least 3 names, shuffled. The sheet never shows which name is gold or which rows are controls, so the annotators cannot tell a miss from a control.

`hard_slice.jsonl` keeps the answer key (`gold`, `kind`, `n_strong_wrong`, `wrong_in`). `labeling_sheet.csv` is the blind sheet.

What the two annotators do, independently, without talking to each other or looking at any model output:

1. Open `labeling_sheet.csv`. For each of the 31 rows read `request_text` and the `candidate_tools` list (names separated by ` | `; descriptions are in `../data/catalog.txt`).
2. Type exactly one name from the list into your column (`annotator_A` or `annotator_B`). Pick the single tool the request needs most directly; the action the user asked for, not a prerequisite step (finding an email is not forwarding it).
3. If no candidate fits, or two fit equally, still pick one and write why in `notes` (e.g. "ambiguous: user never says where the file is").
4. Do not change any other column. Save as CSV. About 15 minutes.

Then: `python3 agreement.py labeling_sheet.csv`. It prints the agreement rate (A == B), each annotator's agreement with gold, the rows where both annotators disagree with gold (likely label errors), the rows where the annotators disagree with each other (genuinely ambiguous), and

```
noise ceiling = 1 - (ambiguous rows) / 180
```

where an ambiguous row is one of those two kinds. Rows not on the sheet were answered correctly by all 14 strong runs and are treated as unambiguous.

Sentence template for the eval slide (the script prints it filled in):

> "Two annotators labeled the 31 hardest rows independently (agreement __%); __ of 180 test rows are ambiguous or mislabeled, so the ceiling on this test set is __._%."

Expectation from the overnight misses analysis: 3 to 5 ambiguous rows (q109 drive-vs-gmail search, q331 notion-vs-db query, q495 zoom-vs-calendar list, q233 forward-vs-search, q119 upload-vs-move), which would put the ceiling near 97 to 98%. glm-5p3-flash's 98.3% ± 0.6 would then be at the ceiling.

## Difficulty tiers (`tiers.json`, `tier_report.py`)

Each test id is tiered by how many of last night's runs got it right. Population: the 27 real runs with accuracy at least 50% (drops only the degenerate nemotron ranked-list run, a format failure). `easy` = every run that scored the row got it right; `hard` = fewer than half did; `medium` = the rest.

| tier | rows | ids (hard) |
|---|---|---|
| easy | 60 | |
| medium | 113 | |
| hard | 7 | q034, q109, q119, q229, q331, q338, q495 |

`python3 tier_report.py <results.json> [...]` prints accuracy per tier for any file with the standard `rows` shape (`id`, `correct`). Last night's runs:

| run | easy | medium | hard | all |
|---|---|---|---|---|
| glm-5p3-flash v1_plain s0 | 100% | 99.1% | 85.7% (6/7) | 98.9% |
| kimi-k3 v1_plain (100 rows) | 100% | 98.6% | 20.0% (1/5) | 95.0% |
| nemotron reasoning-off | 100% | 82.3% | 28.6% (2/7) | 86.1% |

Use: when the tuned catalog-free model is scored, run `tier_report.py` on its results file. Flat accuracy hides whether it lost the easy rows (bad: regression) or only the hard ones (expected: those are the ambiguous rows).

## Adversarial set (`adversarial.jsonl`, `run_adversarial.sh`)

30 new rows, never merged into the locked set, to test whether a model memorised the test distribution or learned the routing. Same gold-first method and same generator (glm-5p3, `gen_adversarial.py`, seed 2026, $0.02): sample a gold tool, pick a same-server rival, then ask for one request that needs the gold and not the rival. Four styles, marked in the `style` field:

| style | rows | what it stresses |
|---|---|---|
| `near_miss` | 8 | a careless reader picks the rival; one concrete detail decides for the gold |
| `two_plausible` | 8 | both gold and rival plausible; exactly one context clue decides |
| `sloppy` | 7 | typos, no capitals, abbreviations |
| `non_native` | 7 | grammar slips, no typos |

30 distinct gold tools, all in the catalog; leak check against the test set: 0 overlap (output above). Each row records its `rival` for error analysis.

`./run_adversarial.sh <model> [run_eval.py args]` scores any model with the same prompt (`../prompts/v1_plain.txt`), scorer and JSON shape as `../run_eval.py`, writes `results_adversarial/<model>__adv__s0.json`, and prints accuracy by style. Smoke run on glm-5p3-flash (2026-11-02, $0.008):

```
near_miss      7/8 = 88%     (adv016 gmail.send_email -> slack.send_message)
non_native     7/7 = 100%
sloppy         7/7 = 100%
two_plausible  8/8 = 100%
all            29/30 = 96.7%
```

Caveat: 30 rows means one miss is 3.3 points; use it as a regression check (did the tuned model fall off on a style?), not as a headline number.

## Spend

`ledger.csv`: $0.0295 total (adversarial generation $0.0212 on glm-5p3, smoke scoring $0.0084 on glm-5p3-flash). Cap for this folder: $2.00 (set in `gen_adversarial.py` and `run_adversarial.sh`).

## Reproduce

```
cd submission/eval
python3 build_slices.py                                   # hard_slice.jsonl, labeling_sheet.csv, tiers.json (offline)
python3 -m pytest test_score.py -v                        # scorer tests
python3 gen_adversarial.py                                # regenerates adversarial.jsonl (new text, temperature 0.8; ~$0.02)
python3 ../../runs/common/check_leak.py ../data/test.jsonl adversarial.jsonl
./run_adversarial.sh glm-5p3-flash                        # ~$0.01
python3 tier_report.py ../../runs/mcp-tool-pick/results/glm-5p3-flash__v1_plain__s0.json
python3 agreement.py labeling_sheet.csv                   # after both annotators fill the sheet
```
