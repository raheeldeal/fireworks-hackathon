# mcp-tool-pick: tool selection over a 100-tool catalog

Pick the single best MCP-style tool (out of 100) for a user request. See `SPEC.md`, results in `RESULTS.md`, pitch in `PITCH.md`, business case in `BUSINESS.md`, judgment calls in `DECISIONS.md`.

## Reproduce every number

```bash
source ~/.zshrc                      # FIREWORKS_API_KEY
cd hackathon/runs/mcp-tool-pick
python3 score.py --test              # 9 scorer unit tests
python3 ../common/check_leak.py data/test.jsonl data/train.jsonl data/train_sft.jsonl
shasum -a 256 data/test.jsonl        # bb50067286893483a60bacd1d86b1a7f33ff5df7b809acb545dd85b085bcaf18
python3 retrieve.py 10               # keyword retriever recall@10 (no API calls)
./run_all.sh                         # all paid runs; idempotent, skips existing results/*.json; waits if the account is suspended
python3 summarize.py                 # RESULTS table from results/*.json
python3 make_chart.py                # frontier.png
python3 fw.py                        # ledger total
```

Single run, for example the rubric prompt on nemotron with reasoning off:
```bash
python3 run_eval.py --model nemotron-lightning-3p5-30b-a3b --prompt prompts/v2_rubric.txt --reasoning none --logprobs --tag v2_rubric+rnone
```
Retrieve-10 variant: add `--retrieve 10`. 5-shot: `--shots 5`. JSON mode: `--prompt prompts/v4_json.txt --json`. Seeds: `--seed 1` (shuffles row order).

Routing (offline, exact at temperature 0, no extra calls):
```bash
python3 route_sim.py results/nemotron-lightning-3p5-30b-a3b__v2_rubric__s0.json results/glm-5p3__v1_plain__s0.json
```

Data regeneration (not needed; `data/test.jsonl` is locked and `split_data.py` refuses to overwrite it):
```bash
python3 build_catalog.py && python3 gen_data.py && python3 split_data.py && python3 sft_prepare.py
```

Fine-tuning (free Muse Glimmer 30B LoRA SFT via REST; output model cannot be scored without a deployment):
```bash
python3 sft_submit.py submit && python3 sft_submit.py poll     # state in results/sft_job.json
```

## Files
- `fw.py` shared client: retries, ledger (`ledger.csv`), $3 cap, price table from `PROTOCOL.md`.
- `run_eval.py` eval runner (same JSON shape as `hackathon/eval/run_eval.py`, plus top-3, token and catalog-share fields).
- `score.py` scorer; `retrieve.py` keyword retriever; `route_sim.py` routing; `summarize.py` table; `make_chart.py` chart.
- `prompts/` v1_plain, v2_rubric, v3_top3, v4_json. `data/` catalog, all/test/train, train_sft.
- `results/` one JSON per run plus logs; `results/_failed_suspended/` the first baseline attempt that hit the account suspension (all rows errored, kept for the record).

## After a run with rate-limit errors
```bash
python3 retry_errors.py results/<file>.json     # re-calls only rows whose call errored, recomputes the summary in place
```
Spend tonight: $2.53 (ledger.csv). Account was suspended 22:03 to 22:15 (HTTP 412); first attempt kept in `results/_failed_suspended/`.
