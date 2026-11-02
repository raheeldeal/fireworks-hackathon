> ## Documentation Index
> Fetch the complete documentation index at: https://docs.fireworks.ai/llms.txt
> Use this file to discover all available pages before exploring further.

# Supervised Fine-Tuning - Text

> Fine-tune Fireworks-hosted text LLMs with supervised learning on your labeled datasets, including LoRA and full-parameter options, formats, and deployment.

This guide will focus on using supervised fine-tuning to train a model and deploy it to an on-demand (dedicated) deployment, which is the only supported method for serving trained models.

For the full list of base models supported by managed training (SFT, DPO, and ORPO) and their max context lengths, see [Models](https://docs.fireworks.ai/fine-tuning/models.md).

## Fine-tuning a model using SFT

**1. Confirm model support for training**

You can confirm that a base model is available to train by looking for the `Tunable` tag in the model library or by using:

```bash theme={null}
firectl model get -a fireworks <MODEL-ID>
```

And looking for `Tunable: true`.

> [!NOTE]
>
> Custom uploaded base models must include a corresponding Hugging Face URL before Fireworks can determine whether they are tunable. Fireworks uses the URL to infer the training renderer and find compatible training shapes. The tunability refresh runs asynchronously about every 30 minutes, so a newly uploaded or updated custom model may take up to 30 minutes to show `Tunable: true`.

> [!NOTE]
>
> Some base models cannot be tuned on Fireworks (`Tunable: false`) but still list support for LoRA (`Supports Lora: true`). This means that users can tune a LoRA for this base model on a separate platform and upload it to Fireworks for inference. Consult [importing trained models](https://docs.fireworks.ai/models/uploading-custom-models.md#importing-trained-models) for more information.

**2. Prepare a dataset**

A dataset is JSONL: one JSON object per line, from 3 to 3 million lines. Each object has a `messages` array and may have a `tools` array of OpenAI function definitions. There is no weight on the example itself. This is the OpenAI chat format, so an existing OpenAI SFT dataset works without conversion.

Each message is an object:

* `role`: `system`, `user`, `assistant`, or `tool`
* `content`: a string, or a list of parts. A text part is `{"type": "text", "text": "..."}`. A thinking part is `{"type": "thinking", "thinking": "..."}`. One text part is the same as a string. Several parts stay separate through the chat template. Image parts are under [Vision training](#vision-training).
* `tool_calls`: optional on an assistant message, and enough on its own when `content` is omitted. Use `{"type": "function", "function": {"name": "...", "arguments": ...}}`, where `arguments` is a JSON object or a JSON string. `{"name": "...", "args": {...}}` is also accepted.
* `weight`: optional number on a message. `0` excludes that message from the loss. Any other number trains it. `trainable` is a boolean for the same switch and wins when both are set.

A `tool` message returns a tool result and should set `tool_call_id`. Assistant thinking can also be a string field, `thinking`, `reasoning`, or `reasoning_content`. When more than one is set, `thinking` is used, then a non-empty `reasoning`, then a non-empty `reasoning_content`. Whether earlier thinking remains in later turns depends on the base model.

> [card] [Thinking history in training](https://docs.fireworks.ai/fine-tuning/thinking-history.md)
>
> Compare every supported model, understand per-user-turn unrolling, configure the job field, and preview what the trainer will see.

```json theme={null}
{"tools": [{"type": "function", "function": {"name": "get_car_specs", "parameters": {"type": "object", "properties": {"trimid": {"type": "integer"}}}}}],
 "messages": [
   {"role": "user", "content": "Specs for trim 121?"},
   {"role": "assistant", "reasoning_content": "Look up the trim.", "tool_calls": [
     {"id": "call_1", "type": "function", "function": {"name": "get_car_specs", "arguments": "{\"trimid\": 121}"}}
   ]},
   {"role": "tool", "tool_call_id": "call_1", "content": "{\"horsepower\": 300}"},
   {"role": "assistant", "content": "300 hp.", "weight": 1}
 ]}
```

**3. Upload a dataset**

Upload the dataset with the Fireworks UI, `firectl`, or the REST API.

> [tab] UI
>
> * You can simply navigate to the dataset tab, click `Create Dataset` and follow the wizard.
>
>   ![Dataset Pn](https://mintcdn.com/fireworksai/3EhcJE4PKaydIoxl/images/fine-tuning/dataset.png?fit=max\&auto=format\&n=3EhcJE4PKaydIoxl\&q=85\&s=0b5955b3abbd38b2725fb2881d57b8ee)

> [tab] firectl
>
> ```bash theme={null}
> firectl dataset create <DATASET_ID> /path/to/jsonl/file
> ```

> [tab] Restful API
>
> You need to make two separate HTTP requests. One for creating the dataset entry and one for uploading the dataset. Full reference here: [Create dataset](https://docs.fireworks.ai/api-reference/create-dataset.md). Note that the `exampleCount` parameter needs to be provided by the client.
>
> ```jsx theme={null}
> // Create Dataset Entry
> const createDatasetPayload = {
>   datasetId: "trader-poe-sample-data",
>   dataset: { userUploaded: {} }
>   // Additional params such as exampleCount
> };
> const urlCreateDataset = `${BASE_URL}/datasets`;
> const response = await fetch(urlCreateDataset, {
>   method: "POST",
>   headers: HEADERS_WITH_CONTENT_TYPE,
>   body: JSON.stringify(createDatasetPayload)
> });
> ```
>
> ```jsx theme={null}
> // Upload JSONL file
> const urlUpload = `${BASE_URL}/datasets/${DATASET_ID}:upload`;
> const files = new FormData();
> files.append("file", localFileInput.files[0]);
>
> const uploadResponse = await fetch(urlUpload, {
>   method: "POST",
>   headers: HEADERS,
>   body: files
> });
> ```

While all of the above approaches should work, `UI` is more suitable for smaller datasets `< 500MB` while `firectl` might work better for bigger datasets.

Ensure the dataset ID conforms to the [resource id restrictions](https://docs.fireworks.ai/getting-started/concepts.md#resource-names-and-ids).

**4. Launch a training job**

There are also a couple ways to launch the training jobs. We highly recommend creating supervised fine-tuning jobs via `UI` .

> [tab] UI
>
> Simply navigate to the `Training` tab, click `New job` and follow the wizard from there. You can even pick a LoRA model to start the training for continued training.
>
> ![Training Pn](https://mintcdn.com/fireworksai/3EhcJE4PKaydIoxl/images/fine-tuning/training.png?fit=max\&auto=format\&n=3EhcJE4PKaydIoxl\&q=85\&s=bef1ff769c8e3f39269fa7943f5d330d)
>
> ![Training Pn](https://mintcdn.com/fireworksai/3EhcJE4PKaydIoxl/images/fine-tuning/train-dialog.png?fit=max\&auto=format\&n=3EhcJE4PKaydIoxl\&q=85\&s=5fd7197004e661df42c147f6aa79106f)
>
> ![Create Sftj Pn](https://mintcdn.com/fireworksai/3EhcJE4PKaydIoxl/images/fine-tuning/create-sftj.png?fit=max\&auto=format\&n=3EhcJE4PKaydIoxl\&q=85\&s=a7e40e746253b43f3d641024e75406a4)

> [tab] firectl
>
> Ensure the trained model ID conforms to the [resource id restrictions](https://docs.fireworks.ai/getting-started/concepts.md#resource-names-and-ids). This will return a training job ID. For a full explanation of the settings available to control the training process, including learning rate and epochs, consult [additional managed training job settings](#additional-managed-training-job-settings).
>
> ```bash theme={null}
> firectl sftj create --base-model <MODEL_ID> --dataset <DATASET_ID> --output-model <FINE_TUNED_MODEL_ID>
> ```
>
> > [!TIP]
> >
> > Similar to UI, instead of tuning a base model, you can also start tuning from a previous LoRA model using
> >
> > ```bash theme={null}
> > firectl sftj create --warm-start-from <FINE_TUNED_MODEL_ID> --dataset <DATASET_ID> --output-model <FINE_TUNED_MODEL_ID>
> > ```
> >
> > Notice that we use `--warm-start-from` instead of `--base-model` when creating this job.

With `UI`, once the job is created, it will show in the list of jobs. Clicking to view the job details to monitor the job progress.

![Sftj Details Pn](https://mintcdn.com/fireworksai/YH2uwOIOrmQeCBpB/images/fine-tuning/sftj-details.png?fit=max\&auto=format\&n=YH2uwOIOrmQeCBpB\&q=85\&s=ff08af5b5df3aa578ac152adb3e33e81)

> [!TIP]
>
> If the trained model appears to learn the wrong text or ignore the expected assistant response, use **Render Samples** on the job details page to inspect the rendered token IDs and loss masks. See [Debug SFT tokenization](https://docs.fireworks.ai/fine-tuning/fine-tuning-models.md#debug-sft-tokenization).

With `firectl`, you can monitor the progress of the tuning job by running

```bash theme={null}
firectl sftj get <JOB_ID>
```

Once the job successfully completes, you will see the new LoRA model in your model list

```bash theme={null}
firectl model list
```

> [!TIP]
>
> For a complete Python SDK example that demonstrates the full workflow
> (creating datasets, uploading files, and launching a supervised fine-tuning
> job), see the [Python SDK workflow
> example](https://github.com/fw-ai-external/python-sdk/blob/main/examples/sftj_workflow.py).

## Deploying a trained model

After training completes, [evaluate the model](https://docs.fireworks.ai/fine-tuning/evaluating-fine-tuned-models.md) before you hold dedicated capacity for production serving.

To deploy for inference:

```bash theme={null}
firectl deployment create <FINE_TUNED_MODEL_ID> --deployment-shape default
```

This creates a dedicated deployment with performance matching the base model. To pick a specific shape instead of `default`, see [Deployment shapes](https://docs.fireworks.ai/guides/ondemand-deployments.md#deployment-shapes).

> [!TIP]
>
> For more details on deploying trained models, including multi-LoRA
> deployments, see the [Deploying Trained Models
> guide](https://docs.fireworks.ai/fine-tuning/deploying-loras.md).

## Additional managed training job settings

Additional tuning settings are available when starting an SFT or preference (DPO/ORPO) job. All of the settings below are optional and have reasonable defaults. For settings that affect tuning quality, such as `epochs` and `learning_rate`, use the defaults first and change them only when the results indicate a clear need. Examples use SFT unless otherwise noted.

> [accordion] Evaluation
>
> By default, the training job will run evaluation by running the trained model against an evaluation set that's created by automatically carving out a portion of your training set. You have the option to explicitly specify a separate evaluation dataset to use instead of carving out training data.
>
> `evaluation_dataset`: The ID of a separate dataset to use for evaluation. Must be pre-uploaded via firectl
>
> ```shell theme={null}
> firectl sftj create \
>   --evaluation-dataset my-eval-set \
>   --base-model MY_BASE_MODEL \
>   --dataset cancerset \
>   --output-model my-tuned-model
> ```

> [accordion] Max Context Length
>
> Depending on the size of the model, the default context size will be different. For most models, the default context size is >= 32768. Training examples will be cut-off at 32768 tokens. Usually you do not need to set the max context length unless out of memory error is encountered with higher lora rank and large max context length.
>
> ```shell theme={null}
> firectl sftj create \
>   --max-context-length 65536 \
>   --base-model MY_BASE_MODEL \
>   --dataset cancerset \
>   --output-model my-tuned-model
> ```

> [accordion] Batch Size (Samples)
>
> Managed SFT and preference tuning use sample-count batching. `batch_size_samples` is the number of SFT samples or preference pairs included in each optimizer step. It is independent of `max_context_length`, which limits the token length of each sample. The UI defaults are 32 samples for SFT and 4 preference pairs for DPO/ORPO.
>
> ```shell theme={null}
> firectl sftj create \
>   --batch-size-samples 32 \
>   --base-model MY_BASE_MODEL \
>   --dataset cancerset \
>   --output-model my-tuned-model
> ```

> [accordion] Epochs
>
> Epochs are the number of passes over the training data. Our default value is 1. If the model does not follow the training data as much as expected, increase the number of epochs by 1 or 2. Epochs must be a whole number.
>
> **Note: we set a max value of 3 million dataset examples × epochs**
>
> ```shell theme={null}
> firectl sftj create \
>   --epochs 2 \
>   --base-model MY_BASE_MODEL \
>   --dataset cancerset \
>   --output-model my-tuned-model
> ```

> [accordion] Learning rate
>
> Learning rate controls how fast the model updates from data. We generally do not recommend changing learning rate. The default value is automatically based on your selected model.
>
> ```shell theme={null}
> firectl sftj create \
>   --learning-rate 0.0001 \
>   --base-model MY_BASE_MODEL \
>   --dataset cancerset \
>   --output-model my-tuned-model
> ```

> [accordion] Learning rate warmup steps
>
> Learning rate warmup steps controls the number of training steps during which the learning rate will be linearly ramped up to the set learning rate.
>
> ```shell theme={null}
> firectl sftj create \
>   --learning-rate 0.0001 \
>   --learning-rate-warmup-steps 200 \
>   --base-model MY_BASE_MODEL \
>   --dataset cancerset \
>   --output-model my-tuned-model
> ```

> [accordion] Learning rate scheduler
>
> Configure how the learning rate changes over training. Supported schedulers are `constant`, `linear`, and `cosine`. When unset, the trainer uses its legacy constant schedule. The same flags apply to SFT and preference tuning jobs (DPO/ORPO).
>
> For `linear` and `cosine`, you can optionally set:
>
> * `--learning-rate-min-lr-ratio`: minimum learning rate as a fraction of `--learning-rate` (0 to 1)
> * `--learning-rate-decay-ratio`: fraction of total training steps over which to decay; `0` decays over the full run
>
> ```shell theme={null}
> firectl sftj create \
>   --base-model MY_BASE_MODEL \
>   --dataset cancerset \
>   --output-model my-tuned-model \
>   --learning-rate 0.0001 \
>   --learning-rate-warmup-steps 10 \
>   --learning-rate-scheduler cosine \
>   --learning-rate-min-lr-ratio 0.1 \
>   --learning-rate-decay-ratio 0.8
> ```
>
> Via the REST API, pass an `lrScheduler` object with one of `constant`, `linear`, or `cosine`:
>
> ```javascript theme={null}
> const payload = {
>   supervisedFineTuningJob: {
>     baseModel: "accounts/my-account/models/MY_BASE_MODEL",
>     dataset: "accounts/my-account/datasets/cancerset",
>     outputModel: "accounts/my-account/models/my-tuned-model",
>     learningRate: 0.0001,
>     learningRateWarmupSteps: 10,
>     lrScheduler: {
>       cosine: {
>         minLrRatio: 0.1,
>         decayRatio: 0.8
>       }
>     }
>   }
> };
> ```

> [accordion] LoRA Rank
>
> LoRA rank refers to the number of parameters that will be tuned in your LoRA add-on. Higher LoRA rank increases the amount of information that can be captured while tuning. The maximum rank depends on the base model's training shape, up to 128; higher values are rejected. `firectl` defaults to 8.
>
> With the REST API or the Python SDK, always set the rank to train a LoRA adapter: `loraRank` in the job body, or `lora_rank` in `supervised_fine_tuning_jobs.create(...)`. An omitted rank is sent as 0, which requests full-parameter training.
>
> ```shell theme={null}
> firectl sftj create \
>   --lora-rank 16 \
>   --base-model MY_BASE_MODEL \
>   --dataset cancerset \
>   --output-model my-tuned-model
> ```

> [accordion] Training progress and monitoring
>
> The training service integrates with Weights & Biases to provide observability into the tuning process. To use this feature, you must have a Weights & Biases account and have provisioned an API key.
>
> ```shell theme={null}
> firectl sftj create \
>   --wandb-entity my-org \
>   --wandb-api-key xxx \
>   --wandb-project "My Project" \
>   --base-model MY_BASE_MODEL \
>   --dataset cancerset \
>   --output-model my-tuned-model
> ```

> [accordion] Model ID
>
> By default, the training job will generate a random unique ID for the model. This ID is used to refer to the model at inference time. You can optionally specify a custom ID, within [ID constraints](https://docs.fireworks.ai/getting-started/concepts.md#resource-names-and-ids).
>
> ```shell theme={null}
> firectl sftj create \
>   --output-model my-model \
>   --base-model MY_BASE_MODEL \
>   --dataset cancerset
> ```

> [accordion] Job ID
>
> By default, the training job will generate a random unique ID for the training job. You can optionally choose a custom ID.
>
> ```shell theme={null}
> firectl sftj create \
>   --job-id my-fine-tuning-job \
>   --base-model MY_BASE_MODEL \
>   --dataset cancerset \
>   --output-model my-tuned-model
> ```

> [accordion] Reservation placement
>
> Reservation placement is off unless you request it. If you request it and your account has an active reservation for the job's accelerator type, the job runs only on that reservation, not on shared trainer capacity. If the account has no matching reservation, the setting is ignored and the job uses shared capacity.
>
> * **firectl**: add `--use-reservation`.
> * **REST**: set `useReservation: true` in the job body.
> * **Python SDK**: pass `use_reservation=True` to `supervised_fine_tuning_jobs.create(...)`.
>
> ```shell theme={null}
> firectl sftj create \
>   --use-reservation \
>   --base-model MY_BASE_MODEL \
>   --dataset cancerset \
>   --output-model my-tuned-model
> ```

### Deprecated parameters

> [!WARNING]
>
> These parameters are deprecated. Do not include them in new managed
> training requests. The wire fields remain present so existing resources can
> still be read, but Training V2 rejects or ignores non-default values as
> described below.

| Proto / Python field | Former or legacy `firectl` flag | Affected jobs | Migration behavior |
| - | - | - | - |
| `batch_size` | `--batch-size` | SFT and DPO/ORPO Training V2 | Training V2 rejects nonzero values; use `batch_size_samples` / `--batch-size-samples`. RFT and RLOR V1 paths are not affected: they still use `batch_size` as the packed-token budget alongside the optional `batch_size_samples` control. |
| `gradient_accumulation_steps` | `--gradient-accumulation-steps` | SFT, DPO/ORPO, RFT, RLOR trainer | Legacy V1 accumulation control. SFT and DPO/ORPO V2 reject nonzero values. Use `batch_size_samples` to control samples or preference pairs per optimizer step. |
| `jinja_template` | — | SFT and shared training config | Training V2 rejects non-empty values. Conversation rendering comes from the base model's registered renderer configuration. |
| `early_stop` | `--early-stop` | Managed SFT | Early stopping is not supported by managed training. The CLI flag is no longer exposed; omit the field or leave it `false`. |
| `mtp_enabled` | `--mtp-enable` | Managed SFT | MTP training is no longer supported. The CLI flag was removed, and managed training rejects `true`. |
| `mtp_num_draft_tokens` | `--mtp-num-draft-tokens` | Managed SFT | Deprecated with MTP support. The CLI flag was removed; leave the field unset (`0`). |
| `mtp_freeze_base_model` | `--mtp-freeze-base-model` | Managed SFT | Deprecated with MTP support. The CLI flag was removed; leave the field unset (`false`). |
| `extra_values` | `--extra-values` (admin-only legacy flag) | Managed SFT | Legacy V1 Helm overrides. Training V2 rejects a non-empty map. |

## Appendix

* `Python SDK` [references](https://docs.fireworks.ai/tools-sdks/python-sdk.md)
* `Restful API` [references](https://docs.fireworks.ai/api-reference/introduction.md)
* `firectl` [references](https://docs.fireworks.ai/tools-sdks/firectl/firectl.md)
* [Complete Python SDK workflow example](https://github.com/fw-ai-external/python-sdk/blob/main/examples/sftj_workflow.py) for a code-only implementation

## Vision training

Vision SFT uses the same `messages` JSONL. Put image parts on `user` messages. Some vision renderers also allow them on `tool` messages. `system` and `assistant` messages cannot contain images. Encode each image as a `data:image/<type>;base64,...` URI before upload, and keep the MIME type accurate (`image/jpeg`, `image/png`).

These parts are the same image:

* `{"type": "image_url", "image_url": {"url": "data:image/jpeg;base64,..."}}`
* `{"type": "image_url", "image_url": "data:image/jpeg;base64,..."}`
* `{"type": "image", "image": "data:image/jpeg;base64,..."}`

Confirm the base model in [Models](https://docs.fireworks.ai/fine-tuning/models.md). Training API VLM loops use these same parts: [Training Shapes](https://docs.fireworks.ai/fine-tuning/models.md#vision-and-multimodal-support).

## Debug SFT tokenization

If the model learns the wrong text or ignores assistant turns, the training renderer may not match inference tokenization.

1. In the dashboard, open your SFT job → **Render Samples** to inspect token boundaries and loss masks.
2. Compare rendered tokens against inference for the same prompt.
3. For custom renderers or agent-driven debugging, use the [training skill — renderer verification](https://github.com/fw-ai/cookbook/blob/main/skills/fireworks-training/references/renderer-verification.md).

> [!NOTE]
>
> In the REST response, the render preview identifies each datum produced from a source row with `examples[].renderings[].renderedDatums[].datumIndex`. Downloaded **Render Samples** use the legacy `split_index` field. The fields play corresponding roles in different schemas; `split_index` has not been renamed in the downloadable artifact.

Common fix: ensure assistant messages you intend to train have non-zero loss weight; system/user turns should be masked out.

### Common findings

| What you see | Likely cause | What to do |
| - | - | - |
| Assistant answer tokens have `token_weights` of `0` | That assistant message has `weight: 0` or `trainable: false`, or the job trains a different span. | Remove the unintended flag from the JSONL row. |
| User or system tokens have positive `token_weights` | The row schema or training configuration is not representing roles as intended. | Verify every message has the correct `role`, and avoid putting assistant text in a `user` message. |
| Expected text is missing from `decoded_tokens` | The source row may have been split, truncated, or rendered differently by the model chat template. | Check `split_index`, source line number, and the job's max context length. |
| Extra special tokens appear around messages | The selected model renderer is adding chat template markers. | This is often expected. If the markers are wrong for your use case, check that the base model and dataset format match. |
| Thinking traces missing from conversation history | The job's thinking-history mode and model renderer decide whether earlier turns' `reasoning_content` is retained. Interleaved removes thinking across user-turn boundaries; Preserved retains it. Datum unrolling is model-specific. | Compare the available modes in the render preview, then verify the created job's mode. See [Thinking history in training](https://docs.fireworks.ai/fine-tuning/thinking-history.md). |
| Token boundaries look surprising | Many tokenizers encode whitespace, Unicode, and byte fallback pieces in non-obvious ways. | Compare with the same Hugging Face tokenizer using `skip_special_tokens=False`. |
| The Render Samples row is missing | The job may predate this feature, may have failed before rendering, or may not have captured samples. | Create a new supervised fine-tuning job, or contact support with the job ID if the job should have rendered samples. |
