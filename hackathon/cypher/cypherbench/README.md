# CypherBench held-out exam for this harness

100 CypherBench test questions on two graphs the model never saw in training (flight_accident, nba), gold rows stored in `test.jsonl` (sha256 in `TEST_HASH`). `run_cb.py` runs this repo's own `run_eval.py` (same harness, same scorer); the only change is that `executor.execute` points at the local CypherBench Neo4j containers.

## 1. Start the two graphs (Docker, ~19 MB of JSON, loads in a few minutes)
```bash
cd hackathon/cypher/cypherbench/docker && docker compose up -d   # ports 15064 (flight_accident), 15067 (nba), auth neo4j/cypherbench
```

## 2. Full ladder in one command (baselines + harness + SFT adapters)
```bash
cd hackathon/cypher && FIREWORKS_API_KEY=... bash cypherbench/run_all.sh
```
Baselines (muse base, glm-5p3-flash, deepseek-v4p1-flash, kimi-k3, plain) run on any key; the two SFT adapters need the adapter owner's key.

## 2b. Only the best system (r6bx_ftbx)
```bash
cd hackathon/cypher
python cypherbench/run_cb.py --tag cb_r6bx_ftbx --model-path vishwajeethogale/run-e9231841f99744a3a291562a0e98cf30/ftbx-56948-f3cd2ac9 \
  --shots 3 --fix --repair 3 --escalate kimi-k3 --data cypherbench/test.jsonl --workers 6 --no-trace
```
Needs the same Python env as `run_eval.py` (fireworks-ai[training], transformers, neo4j). Result: `results/cb_r6bx_ftbx.json`.

## Results so far (this repo's scorer, n=100)
| config | CypherBench | main test (n=200) |
|---|---|---|
| r5_full: Muse Glimmer 30B base + fix + repair 3 + escalate kimi-k3 | 72.0% (CI 62.5-79.9) | 56.0% |
| r6bx_ftbx: SFT LoRA + same harness | pending (needs the adapter owner's key) | 68.5% |

Note: `--shots 3` retrieves same-graph train examples; these two graphs have none, so no examples are used here. This is the intended held-out condition.
