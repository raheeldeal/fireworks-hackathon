> ## Documentation Index
> Fetch the complete documentation index at: https://docs.fireworks.ai/llms.txt
> Use this file to discover all available pages before exploring further.

# Training Overview

> Train an open model on your own data with Fireworks. Start in five minutes with agent skills, then choose Managed Training or the Training API.

Training adapts an open model to your task with your own data. A trained model can beat a larger general-purpose model on quality while costing less and responding faster. Read [when to train your own model](https://fireworks.ai/blog/specialized-intelligence-train-your-own-model).

**Muse Glimmer 30B SFT is free to train until November 30, 2026.**\
No credit card required. [Start here](https://app.fireworks.ai/dashboard/fine-tuning/create?type=supervised\&baseModel=accounts/fireworks/models/muse-glimmer-30b)

## Quickstart

Train your first model in about five minutes with a coding agent such as Cursor, Claude Code, or Codex. You need a [Fireworks account](https://app.fireworks.ai/signup) and an [API key](https://app.fireworks.ai/settings/users/api-keys).

**Step 1: Install the training skills.** Paste this into your agent:

```text wrap theme={null}
Set up Fireworks training for me. Fetch https://docs.fireworks.ai/fine-tuning/agent/use-with-coding-agents.md and follow it.
```

**Step 2: Run your first job.** Ask the agent:

```text wrap theme={null}
Fine-tune Muse Glimmer 30B on the onboarding-prompt-router example dataset.
```

The agent shows you the parameters and cost, then waits for your approval before it starts anything.

**That's it! Now try your own use case.** In the same agent, ask:

```text wrap theme={null}
Train a model to [describe your task] using [your data file or dataset].
```

The skills suggest a method, data format, and evaluation, then plan the job for your approval.

Prefer the UI? Start a job in the [training dashboard](https://app.fireworks.ai/dashboard/fine-tuning).\

Prefer code? Follow [Cookbook: Muse Glimmer First Fine-Tune](https://docs.fireworks.ai/fine-tuning/training-api/cookbook/muse-glimmer.md).

## Ways to train

From self-serve to building with our team:

> [card] [Managed Training](https://docs.fireworks.ai/fine-tuning/managed-finetuning-intro.md)
>
> Bring a dataset and Fireworks runs SFT or DPO for you. Billed per token.

> [card] [Serverless Training](https://docs.fireworks.ai/fine-tuning/training-api/serverless.md)
>
> Write your own training loop on a shared trainer pool. Nothing to provision, billed per token.

> [card] [Dedicated Training](https://docs.fireworks.ai/fine-tuning/training-api/dedicated.md)
>
> Your own loop on GPUs reserved for your run, with full-parameter training and more models. Billed per GPU hour.

> [card] [Fireworks Lab](https://fireworks.ai/contact-training)
>
> Our researchers and engineers build the model with your team, from co-design to a custom build.

Not sure? Start with Managed Training. Move to the Training API when you need a custom loss, reinforcement learning, or inference in the loop ([compare serverless and dedicated](https://docs.fireworks.ai/fine-tuning/training-api/introduction.md#infrastructure)). Choose Fireworks Lab when you want our team to help design and build the model.

## Choose a method

| | Supervised Fine-Tuning (SFT) | Preference Optimization (DPO) | Reinforcement Learning (RL) |
| - | - | - | - |
| **Use it for** | Classification, extraction, format and tone, distillation | Style, helpfulness, or safety, where there is no single right answer | Reasoning and agent tasks where you can score an outcome but can't write the answer |
| **You supply** | Hundreds of good input/output examples | Hundreds to thousands of single-turn chosen and rejected responses | Prompts, often fewer than 100, and a way to score outputs |
| **Runs on** | Managed Training or Training API | Managed Training or Training API | Training API |
| **Guides** | [Text](https://docs.fireworks.ai/fine-tuning/fine-tuning-models.md) · [Vision](https://docs.fireworks.ai/fine-tuning/fine-tuning-models.md#vision-training) · [Cookbook](https://docs.fireworks.ai/fine-tuning/training-api/cookbook/sft.md) | [Managed DPO / ORPO](https://docs.fireworks.ai/fine-tuning/dpo-fine-tuning.md) · [Cookbook](https://docs.fireworks.ai/fine-tuning/training-api/cookbook/dpo.md) | [Agentic RL](https://docs.fireworks.ai/fine-tuning/training-api/cookbook/agentic-rl.md) · [Cookbook](https://docs.fireworks.ai/fine-tuning/training-api/cookbook/rl.md) |

The Training API also runs custom methods such as GRPO and distillation. See [Cookbook recipes](https://docs.fireworks.ai/fine-tuning/training-api/cookbook/overview.md).

## Other ways to run jobs

The agent is the fastest path, and every job is also available directly:

* **Fireworks UI:** create and monitor managed jobs in the [dashboard](https://app.fireworks.ai/dashboard/fine-tuning).
* **`firectl` or the REST API:** script managed jobs and datasets.
* **Python SDK:** write Training API loops, starting from a [cookbook recipe](https://docs.fireworks.ai/fine-tuning/training-api/cookbook/overview.md).

## Next steps

* [Evaluating Trained Models](https://docs.fireworks.ai/fine-tuning/evaluating-fine-tuned-models.md) and [Deploying Trained Models](https://docs.fireworks.ai/fine-tuning/deploying-loras.md) — test your trained model, then serve it
* [Models](https://docs.fireworks.ai/fine-tuning/models.md) — which models each method and surface supports
* [Training cost estimator](https://docs.fireworks.ai/fine-tuning/cost-estimator.md) — estimate a job before you launch it
* [Training GPU quota](https://docs.fireworks.ai/guides/quotas_usage/account-quotas.md#training-gpu-quota) — what your account gets and how to raise it
* [Secure Training](https://docs.fireworks.ai/guides/security_compliance/secure_training.md) — where your data lives, bring your own bucket, and customer-managed keys
