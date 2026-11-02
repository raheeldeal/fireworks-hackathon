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

| Span | Type | Records |
|---|---|---|
| `route` | span | whether the question escalated, which big model, vote agreement |
| `vote` | span | each attempt's query, status and row count; how many agreed; which was taken |
| `attempt` | span | one generate-validate-execute-repair chain: model, final query, status, tokens, cost |
| `schema_prune` | span | schema size before and after, whether pruning applied or fell back |
| `generate` | generation | prompt messages, the model's raw reply, model name, prompt tokens, completion tokens, reasoning tokens, cost, temperature, reasoning effort, latency |
| `validate` | span | the query, the list of schema problems found, whether any was unsafe |
| `execute` | span | graph, the exact Cypher sent, status (`rows` / `empty` / `error`), row count, column names, first rows, the error text, latency |
| `repair` | generation | the second model call, with the problem text it was given; same token and cost fields as `generate` |

Scores on every root trace, as numeric values you can filter and average in the
dashboard:

- `correct` — 1 or 0, execution-equality against the gold rows (only when gold is known)
- `correct_lenient` — 1 or 0, the secondary metric from `score.py`
- `latency_s` — wall seconds for the whole question
- `cost_usd` — total model spend for the whole question

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
```

Graphs: `movies`, `recommendations`, `northwind`, `fincen`, `twitter`.
Configs: whatever `harness/run_harness.py` defines (`plain`, `repair1`,
`prune_repair1`, `repair1_fewshot`, `vote3`, `route_big`, ...).

`--spread` samples across graphs and tiers instead of taking the first N rows, which makes
a better dashboard.

## Opening the dashboard

1. `https://cloud.langfuse.com` → your `text2cypher` project.
2. **Tracing → Traces** for the list. The tag filter gives you one graph or one tier;
   the score columns give you accuracy, latency and cost.
3. **Tracing → Sessions** → the `demo_batch_...` session for a whole batch in one view.
4. Click any trace to get the span tree. `demo_run.py` prints the direct link to the
   question it just ran.

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
| `.pylib/` | The Langfuse SDK, installed with `pip --target` so the shared `.venv` is untouched. |

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
