# Tracing the text-to-Cypher harness

## For a judge, in one paragraph

Every step the system takes on a question is logged. Each question becomes one trace, and
inside it every model call, every schema check, every query execution and every repair is
a separate timed span carrying its own input, output, token counts and dollar cost. You
can open a single question and watch it: the schema being pruned, the small model writing
a query, the validator catching a property that does not exist in the graph, the query
running against the live Neo4j graph and failing, the repair call fixing it, three
independent attempts voting by comparing their result sets, and the escalation to the
large model when they disagree. Each trace carries the answer, whether it matched gold,
its latency and its cost as searchable scores, so the claim "cost per *correct* answer"
can be audited question by question rather than taken on trust.

## What is traced

One root trace per question, named `text2cypher`, tagged with the **graph**, the
**difficulty tier** and the **config** name, and carrying the question as its input and
the final rows as its output. When the gold answer is known the output also carries a
`correct` boolean.

Nested spans, in the order they happen:

Each step is typed as what it actually is rather than a generic span, which is what makes the
Langfuse Agent Graph and the model-level analytics work:

| Span | Type | Records |
|---|---|---|
| `route` | agent | whether the question escalated, which big model, vote agreement |
| `vote` | agent | each attempt's query, status and row count; how many agreed; which was taken |
| `attempt` | chain | one generate-validate-execute-repair chain: model, final query, status, tokens, cost |
| `schema_prune` | retriever | schema size before and after, whether pruning applied or fell back |
| `generate` | generation | prompt messages, the model's raw reply, model name, model parameters (temperature, max tokens, reasoning effort), prompt/completion/reasoning tokens, cost, prompt name and version, latency |
| `validate` | evaluator | the query, the list of schema problems found, whether any was unsafe; `WARNING` on problems, `ERROR` on an unsafe query |
| `execute` | retriever | graph, the exact Cypher sent, status (`rows` / `empty` / `error`), row count, column names, first rows, the error text, latency; `ERROR` on a failed query, `WARNING` when it ran but returned nothing |
| `repair` | generation | the second model call, with the problem text it was given; same token and cost fields as `generate` |

Every trace also carries the Langfuse `environment` (`development`), a `release` and `version`
of `cypher-harness@<test-set hash>`, a `user_id`, a `session_id`, and trace metadata with the
locked test set's sha, the config name and the full config dict. See `BEST_PRACTICES.md`.

Scores on every root trace, as numeric values you can filter and average in the
dashboard:

- `correct` — 1 or 0, execution-equality against the gold rows (only when gold is known)
- `correct_lenient` — 1 or 0, the secondary metric from `score.py`
- `latency_s` — wall seconds for the whole question
- `cost_usd` — total model spend for the whole question

Each score carries a comment saying what was compared, against which test-set hash, and with
how many tokens, so a number in the dashboard can be audited rather than taken on trust. A
fifth score, `exhibit`, is categorical and marks only the handful of traces worth narrating
during the demo.

Batch runs put every question in one Langfuse **session**, so a judge can open the session
and see twenty questions side by side.

## Turning it on and off

Two independent switches. Both are **off by default**, so a scored eval run is byte-for-byte
unaffected.

| Env var | Effect |
|---|---|
| `LANGFUSE_PUBLIC_KEY` (+ `LANGFUSE_SECRET_KEY`) | send spans and scores to Langfuse |
| `LANGFUSE_HOST` | Langfuse base URL, default `https://cloud.langfuse.com` |
| `LANGFUSE_PROJECT_ID` | only needed if the trace link comes back empty (see SETUP.md) |
| `CYPHER_TRACE_LOCAL=1` | build the same span tree in memory and write it to `trace/last_trace.json` |
| `CYPHER_TRACE_ENV` | Langfuse environment, default `development` |
| `CYPHER_TRACE_RELEASE` | Langfuse release, default `cypher-harness@<12 chars of the test-set hash>` |
| `CYPHER_TRACE_USER` | Langfuse user id, default `hackathon-demo` |

With neither `LANGFUSE_PUBLIC_KEY` nor `CYPHER_TRACE_LOCAL` set, `trace()` and `span()`
return a handle whose every method does nothing: no Langfuse import, no network, no tree.
That is the state `harness/run_harness.py` runs in.

**To turn tracing off entirely:** `unset LANGFUSE_PUBLIC_KEY CYPHER_TRACE_LOCAL`.

The two demo scripts set `CYPHER_TRACE_LOCAL=1` for themselves, so they always print a
trace even with no Langfuse account.

## Running it

```sh
source ~/.zshrc                     # FIREWORKS_API_KEY, plus the Langfuse keys if set
cd hackathon/cypher/trace

# one ad-hoc question, printed step by step
../.venv/bin/python demo_run.py --question "Which three directors directed the most movies?" \
    --graph movies --config route_big

# one locked test row, replayed so `correct` is scored
../.venv/bin/python demo_run.py --from-test t000 --config route_big

# 20 locked test rows, so the dashboard has content for judges
../.venv/bin/python demo_batch.py --config route_big --limit 20 --spread

# how the judge set was built: a named session and a tag you can filter on
../.venv/bin/python demo_batch.py --config route_big --limit 30 --spread \
    --session judge_batch30_route_big --tag judge-demo --tag batch30
../.venv/bin/python demo_run.py --from-test t000 --config vote3 \
    --session judge_configs_t000 --tag judge-demo --tag config-comparison
```

`--session` names the Langfuse session, `--tag` is repeatable and appends trace tags, and
`demo_run.py --model <name>` swaps the small model for a fine-tuned checkpoint.

Graphs: `movies`, `recommendations`, `northwind`, `fincen`, `twitter`.
Configs: whatever `harness/run_harness.py` defines (`plain`, `repair1`,
`prune_repair1`, `repair1_fewshot`, `vote3`, `route_big`, ...).

`--spread` samples across graphs and tiers instead of taking the first N rows, which makes
a better dashboard.

## Opening the dashboard

Project: <https://us.cloud.langfuse.com/project/cmvzp74dr0232ad0ewgpdtghe>
(keys are not in this repo; export them inline, see SETUP.md)

1. **Tracing → Traces**, filter tag `judge-demo` for everything built for the demo.
   The score columns give accuracy, latency and cost; the tag filter gives one graph or tier.
2. **Tracing → Sessions** for a whole run in one view. The demo sessions are below.
3. Click any trace for the span tree. `demo_run.py` prints a direct link to what it just ran.
4. Filter the score `exhibit` to jump straight to the four traces worth narrating.

### The judge-ready sessions

| Session | What it is |
|---|---|
| `judge_configs_t000` | all 7 configs on one hard question (t000, recommendations) that every config gets right, so the only difference is cost: 1 model call at $0.00019 vs 3 calls at $0.00059 |
| `judge_configs_t098` | the same 7 configs on a hard fincen question where they disagree: `validate_only`, `prune_repair1` and `repair1_fewshot` get it right, `plain`, `repair1`, `vote3` and `route_big` do not |
| `judge_batch30_route_big` | 30 rows spread across all five graphs and all three tiers on the best config. 46.7% strict, 70% lenient, 0% execution errors, p50 1.8s, $0.0238 total |
| `judge_vote3_repairs` | 26 rows on `vote3`, the run that caught real execution errors and repairs |
| `judge_error_repair` | single-question repair runs on t095 |
| `judge_base_vs_tuned` | the fine-tuned model attempt. **Currently a 404, see below** |
| `diag_error_hunt`, `diag_error_hunt2` | diagnostic sweeps (tag `error-hunt`), not part of the demo |

### The four traces to actually open

| Exhibit | Trace |
|---|---|
| Execution error → repair → rows. Neo4j rejected the generated Cypher with a `CypherSyntaxError`, the repair call rewrote it, the second execute returned a row (t095, movies, hard) | <https://us.cloud.langfuse.com/project/cmvzp74dr0232ad0ewgpdtghe/traces/1ab1c0057472faac9552c7c06dbe755f> |
| Three attempts, real errors and one successful repair: attempt 1 empty → repaired → 3 rows, attempts 2 and 3 repaired into `Unknown function 'year'` (t148, fincen) | <https://us.cloud.langfuse.com/project/cmvzp74dr0232ad0ewgpdtghe/traces/a2b6650c192d4de06589b09aa4ed5c77> |
| Escalation to the big model: 1/3 agreement, below threshold, escalated. $0.00785 against a $0.0006 median — the price of escalation, visible (t038, twitter, hard) | <https://us.cloud.langfuse.com/project/cmvzp74dr0232ad0ewgpdtghe/traces/3c76c3a51e9c5561b836f68eb5ee7f83> |
| Honest failure: all three attempts hit syntax errors and the repair rescued none, so the trace is `ERROR` end to end (t034, movies) | <https://us.cloud.langfuse.com/project/cmvzp74dr0232ad0ewgpdtghe/traces/9af34f08d327ef3637d96239e8e5882e> |

### What to click during the demo

1. **Traces → filter tag `judge-demo`** — one row per question, with `correct`, `latency_s` and
   `cost_usd` as columns. This is the "cost per correct answer" claim, auditable per question.
2. **Sessions → `judge_configs_t098`** — the same question down seven configs. Three get it
   right. Point out that `validate_only` beats `vote3` here at a fifth of the cost.
3. **Open the error → repair trace** (first row of the table above) — walk the span tree: the
   model writes Cypher, the validator passes it, Neo4j rejects it with a syntax error (red,
   level ERROR), the repair call rewrites it, the second execute returns a row.
4. **Open the escalation trace** — 1/3 agreement, so it escalated to the big model, and the
   cost jumps 13x on that one question. The routing policy is visible, not asserted.
5. **Sessions → `judge_batch30_route_big`** — 30 questions across five graphs, 46.7% strict and
   70% lenient, p50 1.8s, $0.0238 for the whole batch. Mention the `environment`, `release` and
   `test_set_sha` on each trace: every number ties back to one locked test set.

## Files

| File | What it is |
|---|---|
| `tracing.py` | `trace()` / `span()` context managers. No-ops unless an env var is set. Also the thread-context propagation and the local-tree pretty printer. |
| `instrument.py` | Wraps the harness functions in spans by swapping the names in the `harness` module namespace. Also the ledger, config lookup and the single-question runner. |
| `demo_run.py` | One question, traced and printed. |
| `demo_batch.py` | N locked test rows, traced with scores attached. |
| `verify_langfuse_path.py` | Proves the Langfuse code path works without an account, by handing the SDK an in-memory OpenTelemetry exporter and asserting the span tree, tokens, cost, tags and session id all arrive. |
| `last_trace.json` | Span tree of the most recent single question. |
| `last_batch.json` | Span trees of the most recent batch. |
| `batch_summary.json` | Accuracy, latency, cost and per-row records for the most recent batch. |
| `ledger.csv` | Every dollar this folder spent. Cap $1, enforced before each call. |
| `batch_summary_judge30.json` | The 30-row judge batch, kept because `batch_summary.json` is overwritten by the next run. |
| `BEST_PRACTICES.md` | Our tracing audited against the official Langfuse skill: what we already did, what changed, and three deliberate deviations. |
| `.pylib/` | The Langfuse SDK, installed with `pip --target` so the shared `.venv` is untouched. |
| `vendor/langfuse-skills/` | The official skill repo, downloaded and read only. Nothing in it is executed or imported. |

## Known issue: the fine-tuned model is not reachable

`demo_run.py --model accounts/raheeldeal/models/cypher-sft-1150` returns
`HTTP 404: Model not found, inaccessible, and/or not deployed`, so the base-vs-tuned
comparison in session `judge_base_vs_tuned` is a single 404 trace, not a comparison. The trace
is still worth a look as proof that API failures surface properly: the generation carries the
404 body and the `attempt` and root are both level `ERROR`. Deploy the checkpoint on Fireworks
and re-run that one command to fill the comparison in.

## How the harness stays unmodified

`harness/harness.py` and `harness/run_harness.py` have **no tracing code in them and were
not edited**. `instrument.install()` replaces seven names in the already-imported
`harness` module (`schema_prune`, `validate`, `_exec`, `call_model`,
`generate_and_repair`, `vote3`, `route`) with wrappers that open a span and call the
original. Because `harness.py` reaches its own helpers through module globals, replacing
the attribute traces the whole chain. Only a process that imports `instrument` is
affected, which means only the two demo scripts.

The harness runs its three vote attempts in a `ThreadPoolExecutor`. Neither a thread-local
stack nor OpenTelemetry's contextvar crosses that boundary on its own, so
`tracing.install_thread_propagation()` patches `ThreadPoolExecutor.submit` to carry both
into the worker. Without it the three attempts would show up as three orphan traces.

## Install

Already done. To redo it:

```sh
cd hackathon/cypher
.venv/bin/pip install --target trace/.pylib "langfuse>=3,<4"
```

`instrument.py` puts `trace/.pylib` on `sys.path` itself, so nothing else needs it.
