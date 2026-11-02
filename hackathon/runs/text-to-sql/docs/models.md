> ## Documentation Index
> Fetch the complete documentation index at: https://docs.fireworks.ai/llms.txt
> Use this file to discover all available pages before exploring further.

# Models

> Base models supported for fine-tuning on Fireworks, with per-model training surfaces (managed, Training API, serverless, dedicated) and method availability.

Managed training, the Training API, and serverless training all draw from the same base model catalog, but availability is decided per model: managed jobs by method (SFT and DPO), Training API jobs by parameter mode (LoRA or full-parameter) and method (SFT, DPO, and RL).

> [!NOTE]
>
> Muse Glimmer 30B SFT is free to train until November 30, 2026.\
> No credit card required. [Start here](https://app.fireworks.ai/dashboard/fine-tuning/create?type=supervised\&baseModel=accounts/fireworks/models/muse-glimmer-30b)

## Model availability

Pick a model to see the surfaces and methods it is enabled for, plus any training shapes that back it. Switch to **All models** for the full matrix.

## Vision and multimodal support

Vision support is model- and surface-specific. Use the catalog above to confirm that the selected VLM has a compatible managed method or Training API shape before preparing data.

* Managed VLM SFT dataset schema and launch flow: [Supervised Fine-Tuning: Vision](https://docs.fireworks.ai/fine-tuning/fine-tuning-models.md#vision-training)
* Training API VLM loops: start from a VLM-compatible shape and the same cookbook SFT, DPO, or RL recipe used for text, replacing the text tokenizer with the model processor
* Inference request formats after deployment: [Vision-language models](https://docs.fireworks.ai/guides/querying-vision-language-models.md)

## Next steps

> [card] [Managed Training](https://docs.fireworks.ai/fine-tuning/managed-finetuning-intro.md)
>
> Hand Fireworks your data and let the platform run the job

> [card] [Training API](https://docs.fireworks.ai/fine-tuning/training-api/introduction.md)
>
> Write your own training loop against a Tinker-compatible API

> [card] [Serverless Training](https://docs.fireworks.ai/fine-tuning/training-api/serverless.md)
>
> Train on shared pooled infrastructure with per-token billing

> [card] [Training Shapes](https://docs.fireworks.ai/fine-tuning/training-api/training-shapes.md)
>
> What a shape pins and how to reference one

> [card] [Dedicated Training](https://docs.fireworks.ai/fine-tuning/training-api/dedicated.md)
>
> Provision a trainer and sampler on reserved GPU capacity

> [card] [Pricing](https://fireworks.ai/pricing)
>
> Current rates across training and inference
