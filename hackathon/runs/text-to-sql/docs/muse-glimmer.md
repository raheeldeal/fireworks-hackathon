> ## Documentation Index
> Fetch the complete documentation index at: https://docs.fireworks.ai/llms.txt
> Use this file to discover all available pages before exploring further.

# Cookbook: Muse Glimmer First Fine-Tune

> Run a free first LoRA fine-tune of Muse Glimmer 30B on Managed SFT or Serverless Training, then measure base versus tuned.

This guide runs a first fine-tune of Muse Glimmer 30B end to end with the
cookbook's [Muse Glimmer starter](https://github.com/fw-ai/cookbook/tree/main/training/examples/muse_glimmer).
The same script runs the job on two surfaces:

* **Managed SFT**: Fireworks runs the training loop on a dataset in your
  account, such as the preloaded prompt-router example: given a user prompt, the
  model returns a compact JSON object that scores its complexity and picks a
  small or big model. This is the quickest first result.
* **[Serverless Training](https://docs.fireworks.ai/fine-tuning/training-api/serverless.md)**: your Python
  process runs the loop on your own chat JSONL on the shared trainer pool, then
  samples the base and tuned adapters in the same session to compare them on
  rows it held out.

> [!NOTE]
>
> Muse Glimmer 30B SFT is free via UI and Serverless Training API until 11/30.
> No credit card required. See [Models](https://docs.fireworks.ai/fine-tuning/models.md). The starter applies
> the promotion to LoRA SFT jobs started before `2026-12-01T00:00:00-08:00` and
> refuses to launch after that unless you pass `--allow-paid`. RL, DPO,
> full-parameter training, deployments, and inference outside the training run
> are not covered.

| Setting | Value |
| - | - |
| Base model | `accounts/fireworks/models/muse-glimmer-30b` |
| Tokenizer | `meta-models/Muse-Glimmer-30B` |
| Renderer | `muse_glimmer` |
| Example datasets | `onboarding-prompt-router` (600 rows) and `onboarding-cord-receipts` (300 rows), preloaded in eligible accounts |
| Default LoRA rank | 8 |

## Quickstart

### Step 1: Install and authenticate

You need Git, Python 3.11 or newer, and a Fireworks API key from the
[dashboard](https://app.fireworks.ai/settings/users/api-keys).

```bash theme={null}
git clone --depth 1 https://github.com/fw-ai/cookbook.git
cd cookbook/training
python3 -m venv .venv && source .venv/bin/activate   # check python3 --version is 3.11+
pip install -e .
export FIREWORKS_API_KEY="fw_..."
```

Run the remaining commands from `cookbook/training`. You can instead put
`FIREWORKS_API_KEY` in a gitignored `.env` file in that directory.

### Step 2: Check the plan

`plan` is read-only. It confirms the account, the example dataset, whether the
promotion is active, and every training parameter before anything is created:

```bash theme={null}
python -m examples.sft.muse_glimmer_starter plan
```

Pass `--surface serverless` to see the Serverless Training plan, including
batch size, sequence length, LoRA alpha, and optimizer settings.

## Managed SFT

### Step 3: Launch and watch

Use a fresh run ID for every run. The run ID names the job and its output model:

```bash theme={null}
RUN=router-$(date +%Y%m%d-%H%M%S)
python -m examples.sft.muse_glimmer_starter launch --surface managed --run-id $RUN
python -m examples.sft.muse_glimmer_starter watch --run-id $RUN
```

`launch` creates a LoRA SFT job on `onboarding-prompt-router` with an automatic
evaluation carve-out. If the run ID already exists, `launch` reuses that job only
when every setting matches and otherwise stops with the differences.

`watch` polls every minute and prints:

* on every poll, the job state and status message (percent complete and epoch,
  or a waiting message while the job waits for a training slot);
* once they are ready, a summary of the platform's rendered training samples:
  token counts, how many tokens carry loss, and image tokens for vision data;
* when the job finishes, train and eval loss from the job's metrics, plus the
  learning rate and steps the platform actually used.

It stops on a terminal state, or if a running job makes no progress for 30 minutes (time waiting in the queue does not count).

A typical run finishes in a few minutes once it starts. In one example run, eval
loss fell from 0.58 to 0.03 over 17 steps. The output is a LoRA model named
`accounts/<account>/models/muse-starter-$RUN`.

> [!NOTE]
>
> Managed SFT reports loss, not task accuracy. Low loss on short, templated
> answers mostly shows the model learned the output format. To measure routing
> accuracy, use the Serverless Training path below, or deploy the model and
> evaluate it on held-out prompts.

### Vision: receipt extraction

The same path trains on receipt images. Image tokens count toward the context,
so 8,192 leaves headroom:

```bash theme={null}
RUN=cord-$(date +%Y%m%d-%H%M%S)
python -m examples.sft.muse_glimmer_starter launch --surface managed --run-id $RUN \
  --dataset onboarding-cord-receipts --max-context-length 8192
python -m examples.sft.muse_glimmer_starter watch --run-id $RUN
```

The `watch` output summarizes a sample of the rendered rows; check that
`tokens_min_max` (image tokens included) is well under the context length.

## Serverless Training with a base-versus-tuned evaluation

This path trains on a local chat JSONL file in the format shown in
[Your own data](#your-own-data).

### Step 3: Prepare the data

`prepare` runs locally and creates nothing on Fireworks. It validates every row,
refuses the file if any row is malformed and lists those rows, holds out 40 rows
(`--n-eval`), and renders one example with the Muse Glimmer tokenizer:

```bash theme={null}
RUN=tickets-$(date +%Y%m%d-%H%M%S)
python -m examples.sft.muse_glimmer_starter prepare --file data.jsonl --run-id $RUN
```

Read the rendered example before you launch: check the token count against
`--max-seq-len` (2,048 by default) and that the trained-token count covers only
the assistant's reply.

### Step 4: Train and evaluate

```bash theme={null}
python -m examples.sft.muse_glimmer_starter launch --surface serverless --file data.jsonl --run-id $RUN
```

The script:

1. Opens a Serverless Training session and samples the base adapter on the
   holdout.
2. Runs one epoch of cross-entropy training at batch size 16, logging loss and
   gradient norm every step. It refuses rows longer than `--max-seq-len`
   rather than truncating them.
3. Samples the tuned adapter on the same holdout with the same decoding
   settings.
4. Promotes the tuned checkpoint to a LoRA model,
   `accounts/<account>/models/muse-starter-sl-$RUN`, before the session closes.
   Pass `--no-promote` to keep it session-only.

It writes these files to `muse_starter_logs/$RUN/`:

| File | Contents |
| - | - |
| `train.jsonl`, `holdout.jsonl` | The prepared splits |
| `metrics.jsonl` | The base evaluation, loss and gradient norm per step, then the tuned evaluation |
| `predictions_base.jsonl`, `predictions_tuned.jsonl` | Per-row answers and scores |
| `summary.json` | Exact match for base and tuned (with per-key accuracy when the answers are JSON), an `unterminated` count (answers that did not stop cleanly), an exact paired McNemar test, and the evaluation sampling token counts |

> [!WARNING]
>
> The promotion covers training. In-session evaluation sampling is priced
> separately at the published per-token rates; the default run samples 80
> answers. `launch` prints a cost line with the sampled token counts.

## Your own data

Both paths take chat JSONL, one example per line:

```json theme={null}
{"messages": [
  {"role": "system", "content": "Classify the ticket. Reply with JSON."},
  {"role": "user", "content": "My invoice is wrong."},
  {"role": "assistant", "content": "{\"category\": \"billing\", \"priority\": \"medium\"}"}
]}
```

`upload` validates every row, refuses the file if any row is malformed or has an
empty assistant reply, and lists those rows. It never drops or rewrites rows
itself. For Managed SFT, fix them in a copy, then upload to a new dataset ID and
train on it:

```bash theme={null}
python -m examples.sft.muse_glimmer_starter upload --file data.jsonl --dataset my-tickets-v1
RUN=tickets-$(date +%Y%m%d-%H%M%S)
python -m examples.sft.muse_glimmer_starter launch --surface managed --run-id $RUN --dataset my-tickets-v1
python -m examples.sft.muse_glimmer_starter watch --run-id $RUN
```

Hold out some rows before uploading so you can compare base and tuned on data
the model has not seen (the Serverless `prepare` step does this split for you). A few hundred clean rows are enough for a first signal.

## Clean up

```bash theme={null}
python -m examples.sft.muse_glimmer_starter cleanup --run-id $RUN
```

Run it once for each run ID you created; each section above sets a new `$RUN`.
`cleanup` deletes the Managed SFT job, its output model, and the promoted
Serverless Training model for that run ID, if they exist. A Serverless Training
session closes when the script exits.

None of these steps leaves anything running. Serving a tuned model requires an
[on-demand deployment](https://docs.fireworks.ai/fine-tuning/deploying-loras.md), which bills per GPU-hour
while replicas run; trained LoRAs cannot be served on serverless inference.

## With a coding agent

The [Fireworks training skills](https://github.com/fw-ai/cookbook/tree/main/skills)
drive this starter for you. Install them, then ask *"Is there something free I can
run right now to see how training works?"*. The agent checks your account, shows
one plan with its cost, launches after you approve, monitors the run, and
reports the results.

## Related guides

* [Serverless Training](https://docs.fireworks.ai/fine-tuning/training-api/serverless.md): the shared trainer pool and its lifecycle
* [Cookbook: Supervised Fine-Tuning](https://docs.fireworks.ai/fine-tuning/training-api/cookbook/sft.md): the general `sft_loop` recipe
* [Deploying Trained Models](https://docs.fireworks.ai/fine-tuning/deploying-loras.md): live merge and multi-LoRA serving
* [Models](https://docs.fireworks.ai/fine-tuning/models.md): surfaces and methods each model supports
