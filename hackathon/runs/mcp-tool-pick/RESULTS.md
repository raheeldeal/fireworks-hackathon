# mcp-tool-pick: tool selection at scale (100-tool catalog)
Status: partial (phase 7 fine-tuning not run: Muse Glimmer 30B SFT is free until 2026-11-30, but this account returns HTTP 403 "dataset uploads are temporarily disabled, please contact Fireworks AI" on both upload endpoints, so no training file could be uploaded. Everything else complete.)
Test set: 180 rows, sha256 bb50067286893483a60bacd1d86b1a7f33ff5df7b809acb545dd85b085bcaf18, source synthetic (gold tool sampled first, 5 styles per tool, text written by glm-5p3; prompt in `gen_data.py`)
Leak check:
```
test set: 180 rows, sha256 bb50067286893483
data/train.jsonl: 320 rows, 0 overlap with test
data/train_sft.jsonl: 320 rows, 0 overlap with test
```
Spend: $2.53 inference, $0.00 training (from ledger.csv; $0.17 data generation, $2.36 evaluation incl. retries of rate-limited rows)

Scoring: top-1 exact match on the tool name; "invalid" = no catalog name in the output (counted as wrong). Temperature 0, max_tokens 1024, model-default reasoning unless the config says `+rnone` / `+rlow`. Latency is wall-clock per call with 4 concurrent workers while nine other agents shared the account, so p95 is pessimistic. `$/1k` is from measured token counts and the PROTOCOL price table. "catalog %" is the share of the per-call cost spent on the catalog's input tokens (about 1,560 of 1,650 input tokens).

## Results table
Full table with every routing threshold: `results/table.md` (regenerate with `python3 summarize.py`). Condensed:

| config | model | accuracy | invalid | p50 s | p95 s | $/1k | catalog % of cost | seeds |
|---|---|---|---|---|---|---|---|---|
| v1_plain (baseline) | nemotron-lightning-3p5-30b-a3b | 81.7% ± 1.4% | 30.7 | 2.48 | 5.11 | 0.216 | 34% | 3 |
| v1_plain (baseline) | glm-5p3-flash | **98.3% ± 0.6%** | 0 | 0.81 | 2.29 | **0.284** | 82% | 3 |
| v1_plain (baseline) | gpt-oss-120b | 92.8% | 0 | 0.42 | 0.81 | 0.296 | 77% | 1 |
| v1_plain (baseline) | deepseek-v4p1-flash | 98.9% | 1 | 0.86 | 1.89 | 0.589 | 87% | 1 |
| v1_plain (baseline) | glm-5p3 | 95.6% | 3 | 0.92 | 3.68 | 2.744 | 81% | 1 |
| v1_plain (baseline, n=100) | kimi-k3 (frontier) | 95.0% | 0 | 1.52 | 4.02 | 6.150 | 76% | 1 |
| v1_plain+rnone (reasoning off) | nemotron | 86.1% | 0 | 0.24 | 1.30 | 0.087 | 90% | 1 |
| v2_rubric+rnone | nemotron | 86.7% | 2 | 0.24 | 1.03 | 0.111 | 75% | 1 |
| v1_plain+5shot | nemotron | 87.8% | 20 | 1.83 | 4.05 | 0.211 | 39% | 1 |
| v2_rubric | nemotron | 76.1% | 41 | 2.67 | 4.88 | 0.252 | 33% | 1 |
| v4_json (json_object mode) | nemotron | 60.0% | 70 | 2.90 | 5.06 | 0.250 | 32% | 1 |
| v3_top3 (ranked list) | nemotron | 6.1% | 169 | 3.13 | 5.47 | 0.291 | 28% | 1 |
| v1_plain+retr10 (keyword top-10) | nemotron | 67.2% | 48 | 2.23 | 4.68 | 0.135 | 6% | 1 |
| v1_plain+retr20 | nemotron | 77.8% | 32 | 1.95 | 3.81 | 0.134 | 12% | 1 |
| v1_plain+rlow | glm-5p3-flash | 96.7% | 0 | 0.56 | 1.12 | 0.253 | 92% | 1 |
| v2_rubric | glm-5p3-flash | 98.3% | 0 | 0.88 | 2.34 | 0.349 | 68% | 1 |
| v1_plain+5shot | glm-5p3-flash | 98.3% | 0 | 0.76 | 1.87 | 0.314 | 77% | 1 |
| v2_rubric+5shot | glm-5p3-flash | 98.1% ± 0.3% | 0 | 0.80 | 1.89 | 0.380 | 64% | 3 |
| v4_json | glm-5p3-flash | 96.7% | 0 | 0.80 | 2.62 | 0.295 | 79% | 1 |
| v3_top3 (ranked list; top-3 hit 98.9%) | glm-5p3-flash | 89.4% | 1 | 1.56 | 3.22 | 0.357 | 65% | 1 |
| v1_plain+retr10 (retrieval recall 70.0%) | glm-5p3-flash | 70.0% | 17 | 0.82 | 6.74 | 0.130 | 20% | 1 |
| route nemotron+rnone -> glm-5p3-flash, logprob < -0.1 (33% escalated) | routing | 97.2% | 0 | 0.33 | 2.31 | 0.184 | - | 1 |
| route nemotron+rnone -> glm-5p3-flash, < -0.2 (16% escalated) | routing | 95.0% | 0 | 0.26 | 2.02 | 0.134 | - | 1 |
| route nemotron+rnone -> glm-5p3-flash, < -0.5 (8% escalated) | routing | 92.2% | 0 | 0.25 | 1.94 | 0.113 | - | 1 |
| route glm-5p3-flash -> glm-5p3, < -0.1 (2% escalated) | routing | 98.9% | 0 | 0.83 | 2.22 | 0.337 | - | 1 |
| route nemotron (default) -> glm-5p3, < -0.1 (16% escalated) | routing | 96.1% | 2 | 2.38 | 6.28 | 0.860 | - | 2 |
| LoRA SFT, catalog-free, Muse Glimmer 30B | fine-tuned | not run (dataset uploads disabled on this account; would be free) | | | | est. 0.03 | 0% | |

Routing is simulated offline from the two result files on the same rows (exact at temperature 0): the small model answers, and when its first-token logprob is below the threshold (or the answer is invalid) the large model's answer on that row is used and both calls are paid. Thresholds swept: -0.02, -0.05, -0.1, -0.2, -0.5, -1.0.

## Best small-model result vs. frontier
The cheapest good configuration is glm-5p3-flash with the plain prompt: 98.3% ± 0.6% over 3 seeds at $0.284 per 1k requests and 0.81 s p50. The frontier open model kimi-k3 scored 95.0% on 100 rows at $6.15 per 1k and 1.52 s p50, so the small model is 3.3 points better, 22x cheaper and 1.9x faster; the mid-size deepseek-v4p1-flash ties it (98.9%, one seed) at 2x the cost.

## Headroom verdict
This is not a task where the frontier model struggles in an interesting way: kimi-k3 misses 5 of 100 and glm-5p3-flash misses 3 of 180, and they miss the same three ambiguous rows (drive vs gmail search, notion vs db query, zoom vs calendar list). The accuracy gap between the best small config and frontier is negative (small wins), and prompting (rubric, 5-shot, JSON) moves glm-5p3-flash by at most ±0.6 points, inside seed noise. Headroom on *accuracy* is therefore about 1.7 points. Headroom on *cost* is large and real: 82% of every call is the catalog, the cheapest model (nemotron, reasoning off, $0.087/1k, 0.24 s) is 12 points behind, and a catalog-free fine-tune would remove the 1,560 catalog tokens from every call (est. $0.03/1k, 10x cheaper than flash). I would not pick this task for the real hackathon as framed (accuracy delta is too small to pitch); I would pick it only if the pitch is re-framed as "cut routing cost 10x at equal accuracy by fine-tuning the catalog into a small model", which needs dataset uploads working and a deployment budget to score the adapter, neither of which this account had tonight. A harder variant (300+ tools, overlapping servers, multi-tool requests) would create accuracy headroom; see `DECISIONS.md` item 9.

## Misses analysis
Best config (glm-5p3-flash, v1_plain, seed 0): 2 misses of 180.
1. `drive.search_files` -> `gmail.search_emails`: "the vendor contract PDF you sent on Nov 14, can you pull up where that lives?" Hypothesis: "you sent" primes email; the request is genuinely ambiguous, every model missed it.
2. `gmail.forward_email` -> `gmail.search_emails`: "That message Ana sent me yesterday ... needs to reach the folks at legal". Hypothesis: the model picks the first step (find the message) rather than the action (forward); a rubric rule for "pick the action, not the prerequisite" did fix this one in v2_rubric.
Seed 1 and 2 added one more each: `notion.query_database` -> `db.run_query` ("filter the candidates board") and `zoom.list_meetings` -> `calendar.list_events` ("what meetings do I have coming up?"). Both are labels where the generator's request does not actually exclude the neighbor; they are arguably label noise (about 1% of the test set).
Frontier (kimi-k3) misses the same rows plus `drive.upload_file` -> `fs.move_file` ("take the pdf from my desktop and put it in the shared folder") and `drive.search_files` -> `slack.search_messages` ("Dana mentioned a deck was uploaded somewhere").
nemotron (reasoning off, 86.1%) misses are different in kind: cross-server confusions driven by surface words, e.g. `jira.search_tickets` -> `github.search_code` ("find all open bugs in the mobile app project"), `stripe.create_subscription` -> `stripe.create_customer` ("put Priya on the $49/mo plan"), `reminders.complete` -> `github.close_issue` ("tick it off"), `gmail.create_draft` -> `github.create_issue`. Hypothesis: it keys on nouns ("bugs", "project") and ignores which system the user is in; these are exactly what a fine-tune or 5-shot fixes (5-shot: +6 points, but default reasoning then overran max_tokens on 20 rows).
Retrieval variant: with keyword top-10 the gold tool is absent for 30% of rows (indirect phrasing never shares words with the description), so accuracy is capped at 70% and the model hallucinates names from outside the shortlist 17 to 48 times. Keyword retrieval is the wrong pre-filter for this data; an embedding retriever would be the next thing to try.

## Gotchas hit tonight
- **Account suspended (HTTP 412 PRECONDITION_FAILED)** from 22:03 to 22:15 for every model: "Account raheeldeal is suspended, possibly due to reaching the monthly spending limit". Not a rate limit. `run_all.sh` polled every 5 minutes and resumed on its own; the failed first attempt is kept in `results/_failed_suspended/`.
- **429 rate limits exhausted 5 retries** on 65 rows across 12 runs (ten agents sharing one account). Those rows were re-called with `retry_errors.py` (only errored rows, never rows that got a response) and summaries recomputed; `retried_errors` in each JSON records the count. Before the retry kimi-k3 showed 92.0% and gpt-oss-120b 85.6%.
- **nemotron thinks itself to death**: with default reasoning it used all 1024 output tokens on 24 to 169 rows (finish_reason "length", empty content, scored invalid), worst with the ranked-list and JSON prompts. `reasoning_effort: "none"` fixes it (0 invalid, 0.24 s, +4.4 points). The PROTOCOL's "max_tokens 512+" is not enough for this model on a 1.7k-token prompt.
- GLM-5.3 models reject `reasoning_effort: "none"` (HTTP 400 "thinking-only model"); `"low"` works but cost glm-5p3-flash 1.6 points.
- `response_format: json_object` hurt both small models (nemotron 60%, flash 96.7%); the plain "reply with only the name" prompt is better.
- **Dataset uploads disabled**: `POST /datasets/{id}:upload` returns 403 "dataset uploads are temporarily disabled, please contact Fireworks AI to get access"; `:getUploadEndpoint` returns 405. Dataset creation itself worked (deleted afterwards). The free Muse Glimmer SFT therefore could not be started. Also, this session's permission classifier blocked `git clone` of the Fireworks cookbook, so the Serverless Training SDK path (the only way to score an adapter without a GPU deployment) was unavailable anyway.
- `run_all.sh` picked the "best small config" for the 3-seed variance run before the rate-limit retries changed the ranking; the plain prompt's extra seeds were run afterwards by hand ($0.10), so both candidates have 3 seeds.
