> ## Documentation Index
> Fetch the complete documentation index at: https://docs.fireworks.ai/llms.txt
> Use this file to discover all available pages before exploring further.

# Evaluating Trained Models

> Evaluate a trained Fireworks model by sampling its serverless checkpoints with the Training SDK, or with a preemptible deployment for a promoted model.

After training, evaluate your model before you hold dedicated capacity for production serving. Choose an evaluation path based on the artifact you have.

> [!WARNING]
>
> These workflows are for **training evals and other non-production workloads only**. Do not send production or latency-sensitive traffic through them. For production serving after eval, create an on-demand deployment. See [Deploying Trained Models](https://docs.fireworks.ai/fine-tuning/deploying-loras.md).

## Which approach to use

Use the path that matches your current training stage:

* **You have a serverless sampler checkpoint:** sample it with the Training SDK, during or after the run.
* **You have a promoted model ID:** use a preemptible deployment. This works regardless of whether the LoRA was trained with serverless, dedicated, or managed training, or imported.
* **Your dedicated training run is still active:** use its inference deployment and refresh it from sampler snapshots. See [Dedicated training and sampling](https://docs.fireworks.ai/fine-tuning/training-api/dedicated.md#training-and-sampling).

| | **Serverless checkpoint sampling** | **Preemptible deployment** |
| - | - | - |
| **Best for** | Quick checks of serverless checkpoints, during or after the run | Evaluating a promoted model without reserving dedicated GPUs |
| **Training path** | Serverless Training API only | Any training path |
| **Artifact** | Sampler checkpoint from `save_weights_for_sampler` | Promoted model (`accounts/<ACCOUNT_ID>/models/<FINE_TUNED_MODEL_ID>`) |
| **API** | Training SDK `sampler.sample()` | Chat Completions or Fireworks SDK |
| **Needs an active training session?** | No | No |

## Serverless checkpoint sampling

Sample a sampler checkpoint from [serverless training](https://docs.fireworks.ai/fine-tuning/training-api/serverless.md) while its base model is available in the [serverless pool](https://docs.fireworks.ai/fine-tuning/models.md). The training session does not need to be active: any process can open a sampler for a checkpoint your account saved. This does not apply to an adapter produced by dedicated training.

There is no serverless chat endpoint for your adapter. Open a **sampling client** bound to a sampler checkpoint. `sampler.sample()` generates completions from that checkpoint, which you score with your own metric.

Use the **sampler checkpoint** returned by `save_weights_for_sampler`, not a promoted model resource (`accounts/<ACCOUNT_ID>/models/<FINE_TUNED_MODEL_ID>`). Promoted models are for on-demand deployment and cannot be passed to `create_sampling_client`.

The following save-and-sample sequence follows the [serverless quickstart](https://docs.fireworks.ai/fine-tuning/training-api/serverless.md#step-4-train-checkpoint-and-sample). Set up `prompt`, `tokenizer`, and `params` as you do for training rollouts.

```python theme={null}
snapshot = training_client.save_weights_for_sampler("eval").result().path
sampler = service.create_sampling_client(model_path=snapshot, tokenizer=tokenizer)
try:
    result = sampler.sample(
        prompt=prompt,
        num_samples=1,
        sampling_params=params,
    ).result()
    for seq in result.sequences or []:
        tokens = list(seq.tokens or [])
        completion = get_text_content(renderer.parse_response(tokens)[0])
        # Score `completion` against your held-out label or grader.
finally:
    sampler.close()
```

`sampler.sample(...)` is the evaluation call. Repeat it over held-out prompts, score each completion with your evaluation metric, then close the sampler. The cookbook's [DeepMath serverless example](https://github.com/fw-ai/cookbook/blob/main/training/examples/rl/deepmath/train_deepmath_serverless.py) shows held-out accuracy evaluation with a math reward.

For checkpoint and promotion details, see [Saving and loading checkpoints](https://docs.fireworks.ai/fine-tuning/training-api/serverless.md#saving-and-loading-checkpoints) on the serverless training page.

### After the run ends

You do not need a training client to sample a checkpoint: open a sampler from a fresh service client with the checkpoint path that `save_weights_for_sampler` returned. See [Sampling without a training client](https://docs.fireworks.ai/fine-tuning/training-api/serverless.md#sampling-without-a-training-client) on the serverless training page, which also covers running evaluation across worker processes.

> [!NOTE]
>
> Promote checkpoints you want to keep long term or serve through the chat completions API, then evaluate the promoted model with a [preemptible deployment](#preemptible-deployment) below.

## Preemptible deployment

If you want to evaluate a promoted model without holding dedicated on-demand capacity, create a **preemptible deployment**. It borrows idle reserved GPU capacity instead of reserving GPUs exclusively for you.

For LoRA, this includes adapters trained with serverless, dedicated, or managed training, as well as imported adapters. Point the deployment at your promoted fine-tuned model ID, not the base model.

It can be reclaimed (preempted) at any time. Fireworks does not guarantee how many GPUs are available or how long the deployment stays up, but in practice it typically lasts long enough to finish a training eval.

### How it works

Passing `--preemptible` to `firectl deployment create` opts the deployment into capacity borrowing:

* The deployment runs on reserved nodes that are currently idle.
* When the capacity owner needs those GPUs back, your deployment can be preempted.

Because it borrows idle capacity, you do not need to hold dedicated on-demand capacity for the duration of the eval.

### Requirements

`--preemptible` takes effect only on **firectl 1.7.26 or newer**. Check with `firectl version`. The flag is not present in older builds. Upgrade if you are below 1.7.26.

### Behavior

* **Training evals only.** A preemptible deployment can be preempted mid-request. Treat disappearance as a normal outcome, not an error.
* **`--preemptible` is immutable.** It is set at create time and cannot be toggled on or off afterward. To change it, delete the deployment and create a new one.
* **Clean up when done.** Delete the deployment after your eval so you stop holding the borrowed capacity.

### Create the deployment

```bash theme={null}
firectl deployment create accounts/<ACCOUNT_ID>/models/<FINE_TUNED_MODEL_ID> \
  --deployment-id <YOUR_DEPLOYMENT_ID> \
  --display-name <YOUR_DISPLAY_NAME> \
  --deployment-shape default \
  --min-replica-count 1 \
  --max-replica-count 1 \
  --preemptible
```

Replace the placeholders:

* `<FINE_TUNED_MODEL_ID>`: the trained model to eval, not a base model.
* `<YOUR_DEPLOYMENT_ID>` / `<YOUR_DISPLAY_NAME>`: a name of your choice for the eval deployment.

`--deployment-shape default` has Fireworks pick a validated shape (for fine-tuned models, matched against the model's base model). To pick a specific shape, see [Deployment shapes](https://docs.fireworks.ai/guides/ondemand-deployments.md#deployment-shapes).

### Worked example

```bash theme={null}
firectl deployment create accounts/<ACCOUNT_ID>/models/<FINE_TUNED_MODEL_ID> \
  -a <ACCOUNT_ID> \
  --deployment-id <FINE_TUNED_MODEL_ID>-eval \
  --display-name <FINE_TUNED_MODEL_ID>-eval \
  --deployment-shape default \
  --min-replica-count 1 \
  --max-replica-count 1 \
  --preemptible
```

### Run the eval and tear down

Check that the deployment is ready, then send eval requests to the trained model:

```bash theme={null}
firectl deployment get <YOUR_DEPLOYMENT_ID> -a <ACCOUNT_ID>
```

```bash theme={null}
curl https://api.fireworks.ai/inference/v1/chat/completions \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $FIREWORKS_API_KEY" \
  -d '{
    "model": "accounts/<ACCOUNT_ID>/models/<FINE_TUNED_MODEL_ID>",
    "messages": [
      {
        "role": "user",
        "content": "Hello!"
      }
    ]
  }'
```

When the evaluation is finished, delete the deployment to release the borrowed capacity:

```bash theme={null}
firectl deployment delete <YOUR_DEPLOYMENT_ID> -a <ACCOUNT_ID>
```

For more on preemptible capacity and guarantees, see [Preemptible deployments](https://docs.fireworks.ai/guides/ondemand-deployments.md#preemptible-deployments-eval-batch) in the on-demand deployments guide.

## Next steps

> [card] [Deploying Trained Models](https://docs.fireworks.ai/fine-tuning/deploying-loras.md)
>
> Live merge or multi-LoRA for production serving
