# Harness status

Updated 12:05 PT. **Done.** Spend $2.41 of $6 (`ledger.csv`). No deployments.

## Files
- `harness.py`: validate, generate_and_repair, vote3, route, schema_prune, retrieve_examples.
- `run_harness.py --config <name> [--reasoning low|default] [--seed N]`: scores one config, writes `results/harness_<config>.json`.
- `report.py`: rebuilds `HARNESS_TABLE.md` and `CALIBRATION.md` from the results files.
- `HARNESS.md`: results table, repeated runs, per-tier, one paragraph per element, decisions for a human.
- `CALIBRATION.md`: accuracy by vote agreement, per run and pooled.
- `run_all.sh`: the six configs in the agreed order.

## Result in one paragraph
Plain glm-5p3-flash: 53.0% (3 runs). Best harness, repair1 at default reasoning: 53.3% (3 runs). vote3 51.7%, route_big 51.9% (4 runs; the first run's 55.0% was the high end). The harness cuts failed or empty queries from 2.2% to 0.3% and gives a confidence signal (3/3 agreement 62% correct, 2/3 35%, none 18%), but does not move accuracy beyond noise. Most misses run cleanly and return different rows from gold; lenient scoring puts the same answers at about 65%.

## Gotchas
- `reasoning_effort: none` is rejected for GLM-5.3 flash ("thinking-only model"); `low` works and costs 3 to 5 points vs default.
- The dataset has two schema text formats (bulleted and `Label {prop: TYPE}`); the validator parses both.
- Temperature 0 is not deterministic: 9 of 190 untouched rows flipped between two runs.
- 4 gold queries use properties absent from the graph (t020, t047, t083, t138).
- Two 6-row smoke-test files were overwritten by the full runs; nothing stale remains in `results/`.
