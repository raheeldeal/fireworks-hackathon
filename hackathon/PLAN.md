# One-page plan: "Fine-tune to delete the prompt"

**Thesis.** On narrow tasks the frontier premium buys nothing (measured: 9 of 10 tasks, 30k calls overnight). The remaining lever is tokens. We fine-tune a small model so it needs no catalog in the prompt and no hidden reasoning: accuracy flat, cost down 5 to 10x, latency down 3x. The frontier chart moves left.

**Task.** Tool routing: user request → one of 100 MCP-style tools. Baseline sends the 1,560-token catalog on every call (82% of cost). Locked test set: 180 rows, sha256 bb50067286893483. Stock small model: 98.3% ± 0.6 at $0.28/1k. Frontier kimi-k3: 95.0% at $6.15/1k.

**Deliverable at 4:00.** Deployed catalog-free LoRA, curl'd live next to the stock model; frontier chart with 6+ points; eval slide with hash, scorer tests, human-verified hard slice, stated ceiling; business slide with $/day at 1M calls; repo README that reproduces every number.

## Timeline and owners
| Time | Workstream | Owner | Done when |
|---|---|---|---|
| 10:00 | **Unblock account**: tell a Fireworks mentor "dataset uploads are disabled on account raheeldeal (HTTP 403), please enable" and ask for event credits + the deploy command | Raheel | Upload works, or a teammate's account is used |
| 10:00 | Lock task, thesis, workload (1M calls/day) on the whiteboard | Raheel | Team agrees in 15 min |
| 10:15 | Rerun model sweep on tool routing (scripted, `run_baselines.sh`), add prompt-vs-answer token split | Eng A | Table by 11:00 |
| 10:15 | Human hard slice: two people label the 30 hardest rows independently; count agreement; state ceiling | Raheel + Eng C | Ceiling number by 11:30 |
| 10:30 | Catalog-free LoRA SFT on `data/train_sft.jsonl` (320 rows) via Serverless Training API (no upload needed) | Eng B | Job running by 11:30 |
| 11:00 | RFT: reward = correct tool AND no catalog AND short output; run as rejection-sampling loop on the training API if managed RFT is still blocked | Eng B | Second tuned model by 14:30 |
| 11:30 | Reasoning on/off, max_tokens 512 vs 4096; save the empty-response artifact for the demo | Eng A | 30 min |
| 12:00 | Routing + calibration from sweep files (offline, no calls) | Eng A | 30 min |
| 13:00 | Score tuned models on the locked set; difficulty tiers (easy/med/hard) | Eng B | 14:30 |
| 14:30 | Deploy tuned LoRA (dedicated, 2 hours, event credits), measure p50, record side-by-side curl video | Eng B | 15:30 |
| 14:00 | Chart, BUSINESS.md, PITCH.md, README | Raheel | 15:30 |
| 15:30 | Rehearse twice, timed. Tear down deployment after demo | All | 16:00 submit |

## Pitch (3 min)
1. "We ran ten tasks and 30,000 calls last night. The frontier model never beat the cheap one. So accuracy isn't the lever; tokens are."
2. The task, the eval (hash, scorer tests, human ceiling 9x%).
3. Live: stock model with 1,800-token prompt vs tuned model with 300-token prompt, same answer, faster, cost printed.
4. Chart: frontier moved left. Business: $/day at 1M calls, before and after.
5. How far: SFT vs RFT vs prompt; what didn't work (prompting hurt; legal fine-tune tied).

## Risks
Upload stays disabled → use a teammate's account or the training API. Deployment credits absent → score via training-API sampler, show latency from the stock small model, say so. RFT fails → SFT alone, present honestly.
