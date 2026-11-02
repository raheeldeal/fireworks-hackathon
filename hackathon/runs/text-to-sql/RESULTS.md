# text-to-sql
Status: partial (Fireworks account suspended at 22:04 PT, HTTP 412 on every call; paid phases 4-7 waiting on the account. Offline phases 1-3 complete; phases 4-5 are scripted in run_all.sh, phase 7 in sft_serverless.py, and a background waiter starts them the moment the account answers.)
Test set: 180 rows, sha256 4efe94e1f88833af1d52aff4baedcac0740ba90def88edac4a87b45bd426afbd, source https://huggingface.co/datasets/HAL-9001/spider-databases (re-host of Spider 1.0 dev split, https://yale-lily.github.io/spider)
Leak check:
```
test set: 180 rows, sha256 4efe94e1f88833af
data/train.jsonl: 450 rows, 0 overlap with test
data/sft_train.jsonl: 450 rows, 0 overlap with test
```
Spend: $0.00 inference, $0.00 training (from ledger.csv)

## Results table
| config | model | accuracy | invalid | p50 s | p95 s | $/1k | seeds |
| (none yet: account suspended) | | | | | | | |

## Best small-model result vs. frontier
Not yet measured.

## Headroom verdict
Not yet measured. Prior: published Spider dev execution accuracy for strong LLMs with plain prompting is roughly 70-85%, so a frontier model will likely leave 15-25 points of headroom, and SFT on 450 in-distribution examples typically adds 5-10 points to a small model.

## Misses analysis
Pending.

## Gotchas hit tonight
- Google Drive quota exceeded for the official Spider zip; used the HF re-host HAL-9001/spider-databases, checksum verified.
- Hugging Face datasets-server rows API rate-limits at ~100 requests (429) when paging the 7,000-row train split; retried with backoff.
- Fireworks account suspended (HTTP 412 PRECONDITION_FAILED) on both inference and control-plane endpoints, ~22:04 PT.
