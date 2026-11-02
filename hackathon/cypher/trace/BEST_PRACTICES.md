# Our tracing against the official Langfuse skill

The skill is the `langfuse` skill from <https://github.com/langfuse/skills>, downloaded to
`trace/vendor/langfuse-skills/` and read, not executed. Its instrumentation guidance lives in
`skills/langfuse/SKILL.md` and `skills/langfuse/references/instrumentation.md`, and it tells you
to audit against the live page
<https://langfuse.com/docs/observability/best-practices> rather than from memory, which is what
was done here. Exact SDK field names were then confirmed against the vendored SDK
(`trace/.pylib`, langfuse 3.15.0) rather than guessed.

Everything below was applied by editing **our** files only: `tracing.py`, `instrument.py`,
`demo_run.py`, `demo_batch.py`, `verify_langfuse_path.py`. No harness, train, audit, score,
executor or data file was touched, and tracing is still off unless an env var turns it on.

## What we already did right

| # | Skill recommendation | Where we already met it |
|---|---|---|
| 1 | Nest multi-step work; one generation per model call, not one wrapping the loop | `instrument.py` wraps seven harness functions, so a vote run is 15 nested observations with one `generate` per actual API call |
| 2 | Descriptive, stable observation names | `text2cypher`, `generate`, `validate`, `execute`, `repair`, `vote`, `route` — verb-first, no model names, no dynamic values |
| 3 | Model name on every generation | `model=` was already set from the harness's model string |
| 4 | Token usage so cost can be computed | `usage_details` with input/output/total |
| 5 | Explicit cost | `cost_details` from the harness `PRICING` table |
| 6 | Meaningful trace input and output, explicitly set (not raw function args) | root carries the question and the final rows, not `**kwargs` |
| 7 | Messages in OpenAI role/content form | the generation input is the real message list |
| 8 | Capture reasoning | `reasoning_tokens` and `reasoning_effort` were already recorded |
| 9 | Tags for dimensions known at creation | graph, tier and config name |
| 10 | Scores for things decided after the fact | `correct`, `correct_lenient`, `latency_s`, `cost_usd` |
| 11 | `flush()` before a script exits | explicit flush in each demo's `finally`, plus an `atexit` hook |
| 12 | Sessions to group related traces | batch runs already shared one session id |

## What we were missing, and what changed

| # | Gap the skill flagged | Before | After |
|---|---|---|---|
| 1 | **Environment attribute** so demo traces never pollute a production dashboard | not set, everything landed in `default` | `Langfuse(environment=...)`, `development` by default, override with `CYPHER_TRACE_ENV` |
| 2 | **Release / version** pinning a trace to a build | not set | `release=` and trace `version=` set to `cypher-harness@<12 chars of the test-set hash>`; there is no git here, and the locked test set is what actually decides whether two runs are comparable. Override with `CYPHER_TRACE_RELEASE` |
| 3 | **`user_id`** for per-user filtering and cost attribution | not set | `hackathon-demo`, override with `CYPHER_TRACE_USER` |
| 4 | **Correct observation types**, not a generic span for everything; this is what drives the Agent Graph | every non-model step was `span` | `route` and `vote` are `agent`; `attempt` is `chain`; `validate` is `evaluator`; `schema_prune` and `execute` are `retriever`; `generate` and `repair` stay `generation` |
| 5 | **`model_parameters`** as a first-class field, not buried in metadata | temperature and reasoning effort sat in `metadata` | `model_parameters={temperature, max_tokens, reasoning_effort}` on every generation, so the UI shows them and you can compare across them |
| 6 | **Prompt identity on each generation** | nothing | `prompt_name` (`cypher-generate` / `cypher-repair`) plus `prompt_version`, a 12-char hash of the system prompt actually sent. See the caveat below |
| 7 | **Trace metadata a judge can filter on** | graph, tier, config, row id | adds `test_set_sha` (from `../data/TEST_HASH`), `release`, `environment`, `config_detail` (the full config dict), `small_model`, `big_model`, `gold_known` |
| 8 | **Masking of sensitive data** | none, on the argument that there is none | a `mask` hook on the client redacts anything shaped like a credential (Fireworks `fw_`, Langfuse `pk-lf-`/`sk-lf-`, generic `sk-`, `Bearer` headers, `api_key=`). Defence in depth, not a fix for a known leak |
| 9 | **Error level and status message on failures** | only an uncaught exception or a failed execute set `ERROR` | `execute` marks `WARNING` when it runs but returns nothing; `validate` marks `WARNING` on schema problems and `ERROR` on an unsafe query; `attempt` marks `ERROR` on failure and `WARNING` when it needed a repair; the root marks `ERROR` on a failed query and `WARNING` when it ran clean but missed the gold answer, each with a one-line `status_message` |
| 10 | **Score comments** so a number is auditable | only `correct` had a comment | all four scores carry a comment naming what was compared, the token split, the config and the test-set hash |
| 11 | **Stable session per demo run** | `demo_run.py` hardcoded `session_id="demo_run"`, so every single-question run in history collapsed into one session | `demo_run_<config>_<HHMMSS>`, with `--session` to name it |
| 12 | **Findable traces** | tags were fixed to graph/tier/config | `--tag` on both demos appends arbitrary trace tags, which is how the judge set is tagged `judge-demo` |
| 13 | **Flush semantics at exit** | `atexit` called `flush()`, which empties the queue but leaves the exporter running | `atexit` now calls `shutdown()`, which flushes *and* stops the exporter, so a process exiting mid-export cannot drop the tail |

## Three deliberate deviations

1. **Span names were not changed to the skill's hyphenated style** (`prune-schema` rather than
   `schema_prune`). The same page says names are stable identifiers that dashboards and
   evaluators match on. Renaming mid-hackathon would split the dashboard into traces with old
   names and traces with new names, which costs a judge more than the naming style gains.

2. **Prompts are not managed Langfuse prompts.** The skill prefers fetching prompt text from
   Langfuse so each generation links to a prompt version. The prompt templates live in
   `harness/harness.py`, which is off limits, and pointing a generation at a Langfuse prompt we
   do not actually send would be a lie in the dashboard. Instead each generation records the
   prompt's role name and a hash of the exact system prompt sent, which is enough to tell
   few-shot from zero-shot and pruned schema from full schema. Real prompt management is the
   one remaining gap and needs a harness edit.

3. **No framework integration.** The skill prefers an integration over manual instrumentation.
   The harness calls Fireworks over raw HTTP and must not be edited, so monkey-patching seven
   module-level names is the only way in. It is manual, but it is also why the scored eval runs
   stay byte-for-byte untouched.

## Verifying the claims

`verify_langfuse_path.py` runs the whole Langfuse path against an in-memory OpenTelemetry
exporter, with no account and no network, and now also asserts:

- each step's observation type (`agent`, `chain`, `evaluator`, `retriever`, `generation`)
- `model_parameters` and `prompt_name` reach the generation
- `user.id` and `langfuse.version` reach the trace, and the test-set hash loaded
- five credential shapes are redacted by `mask()` while ordinary Cypher is untouched
- no credential-shaped string appears in any exported span

```sh
cd hackathon/cypher/trace && ../.venv/bin/python verify_langfuse_path.py
```

**On credentials in spans:** a live trace was fetched back from the API and searched. No
Fireworks key, secret key, bearer header or `FIREWORKS_API_KEY` appears anywhere in it. The one
key-shaped string present is the Langfuse **publishable** key, which the Langfuse SDK itself
stamps into its instrumentation-scope attributes to say which project sent the span. That is
Langfuse's own field, not ours, and the secret key never appears.
