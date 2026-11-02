# Working in parallel (4 people, one repo)

## Shared, do not edit
- `data/test.jsonl` — the 200-question exam. Locked. Fingerprint in `data/TEST_HASH`.
  Re-read the hash at the start of every run and assert it matches. If you need to change the exam,
  tell the team; a changed exam invalidates every number already on the slides.
- `executor.py` — runs Cypher read-only on the live graphs.
- `score.py` — grading. If you believe a rule is wrong, add `score_v3` next to it; don't change existing functions.
- `data/train.jsonl` — the 500 teaching questions. Add new training files as new names.

## Your own folder (edit freely, nobody else touches it)
| Folder | Owner | What goes here |
|---|---|---|
| `harness/` | Eng 1 | validate, repair, vote, route, prune (built) |
| `harness2/` | Eng 2 | second harness approach |
| `bench2/` | Eng 3 | second benchmarking exercise |
| `train/`, `train2/` | Eng 4 | fine-tuning |
| `trace/` | shared | Langfuse tracing (default off) |
| `review/` | Raheel | eval-set review sheet |
| `audit/` | Claude | scorer audit and re-scoring |

## Results format (so one chart shows everyone's work)
Write every scored run to `results/<yourname>_<config>.json` with at least:
`{"model":…, "prompt":…, "n":…, "accuracy":0.0-1.0, "error_rate":…, "empty_rate":…,
 "p50_latency_s":…, "p95_latency_s":…, "cost_per_1k_requests_usd":…,
 "rows":[{"id":"t000","tier":"easy","graph":"movies","pred_cypher":"…","exec_status":"correct|wrong|error|empty","correct":true,"latency":…,"in_tokens":…,"out_tokens":…}]}`
`make_charts.py` picks up anything with that shape. Keep per-row data: the tier tables, calibration and
coverage curve are all computed from it.

## Git hygiene
`git pull --rebase` before every push. Small commits. Never commit `.venv/`, `raw/`, `*.sqlite`, `.pylib/`.
If two people must touch a shared file, say so in the group chat first.

## Spend
Each person keeps a `ledger.csv` in their folder: model, in_tokens, out_tokens, cost. Cap yourself at $5.
