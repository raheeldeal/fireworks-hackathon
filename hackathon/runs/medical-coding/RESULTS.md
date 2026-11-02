# Clinical note -> ICD-10-CM category codes
Status: partial (baselines running)
Test set: 180 rows, sha256 0b38626382177f568d2b282e37a1114dc6e7a0e7271f2c92558a0322a24518e7, source synthetic (glm-5p3, labels sampled first; see SPEC.md and gen_data.py)
Leak check:
```
test set: 180 rows, sha256 0b38626382177f56
data/train.jsonl: 314 rows, 0 overlap with test
```
Spend: $0.08 inference, $0.00 training (from ledger.csv)

## Results table
| config | model | accuracy (set-F1) | exact | invalid | p50 s | p95 s | $/1k | seeds |
|---|---|---|---|---|---|---|---|---|
| pending | | | | | | | | |

## Best small-model result vs. frontier
pending

## Headroom verdict
pending

## Misses analysis
pending

## Gotchas hit tonight
- glm-5p3 is thinking-only; `reasoning_effort: "none"` returns 400. `reasoning_effort: "low"` is accepted and cuts hidden reasoning from ~600 tokens/note to ~1. Two 10-note generation calls hit `finish_reason=length` at 6000 tokens before this fix ($0.055 wasted).
- Random care-setting pairings in the generation prompt (nephrology clinic + psoriasis only) made the model deliberate for ~2000 tokens; letting the model pick the setting fixed it.
- HTTP 412 "Account raheeldeal is suspended, possibly due to reaching the monthly spending limit" at 22:04, before any note was generated. Ten parallel runs likely hit the account's monthly cap. Only the owner can clear it.
