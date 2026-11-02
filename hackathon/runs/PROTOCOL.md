# Overnight run protocol (read fully before starting)

You are one of ten parallel agents, each running a complete mock hackathon for one task, overnight, unattended. The user is asleep. A judge session re-runs your numbers in the morning, so everything must be reproducible from your folder. Do not ask the user questions; make a reasonable call, write it down in `DECISIONS.md`, and continue.

## Hard rules (violating any of these ends the run)

1. **Work only inside your folder** `hackathon/runs/<task>/`. Never edit files outside it except reading `hackathon/eval/` and `hackathon/runs/common/`.
2. **Spend cap: $3.00 on inference** for this run, computed from token counts × the price table below. Keep a running ledger in `ledger.csv` (timestamp, model, in_tokens, out_tokens, cost). Stop all paid calls when the ledger total reaches the cap and write what's missing in `RESULTS.md`.
3. **No dedicated / on-demand deployments.** Never run `firectl deployment create`, never create a GPU deployment via SDK or UI. They bill per GPU-hour and will blow the whole night's budget. If the only way to score a tuned model is a dedicated deployment, do not do it; document the exact command you would run and mark the row "not scored (dedicated deployment required)".
4. **Paid SFT only if your brief says you have SFT budget.** One job, LoRA, base model under 16B, training file under 300k tokens (≈ $0.15 at $0.50/M). RFT or other training only if the docs and the job creation page confirm it is free; log the evidence in `DECISIONS.md`. If a training command shows a price you did not expect, abort it.
5. **Lock the test set before anything else.** Write `data/test.jsonl` (150 to 200 rows), run `python3 ../common/check_leak.py data/test.jsonl` and record the sha256 in `RESULTS.md`. Never modify it afterwards. Every training file must pass `check_leak.py` against it; put the output in `RESULTS.md`.
6. **Temperature 0, max_tokens 512+ for reasoning models.** Several Fireworks models think before answering; content can come back empty or `None`. Handle it (see `hackathon/eval/run_eval.py`).
7. **Retry with backoff on 429/5xx**, up to 5 times. Rate limits are expected with ten agents running.
8. **Python:** 3.10 is installed via pyenv. If Fireworks tooling needs 3.11+, `pyenv install 3.11` into a venv inside your folder. Install packages only into that venv.

## Model ids and prices (serverless standard, $ per 1M tokens, verified 2026-11-01)

| Model id | Input | Output | Role |
|---|---|---|---|
| accounts/fireworks/models/nemotron-lightning-3p5-30b-a3b | 0.05 | 0.20 | small (NVIDIA, co-host) |
| accounts/fireworks/models/glm-5p3-flash | 0.15 | 0.50 | small |
| accounts/fireworks/models/gpt-oss-120b | 0.15 | 0.60 | medium |
| accounts/fireworks/models/deepseek-v4p1-flash | 0.30 | 1.20 | medium |
| accounts/fireworks/models/glm-5p3 | 1.40 | 4.40 | large |
| accounts/fireworks/models/kimi-k3 | 3.00 | 15.00 | frontier open (use sparingly: 200 calls ≈ $1) |

Endpoint: `https://api.fireworks.ai/inference/v1/chat/completions`, key in `$FIREWORKS_API_KEY` (already in `~/.zshrc`; `source ~/.zshrc`). Fine-tuning: LoRA SFT ≤16B is $0.50 per 1M training tokens. Docs index: https://docs.fireworks.ai/llms.txt. Fireworks also publishes Claude Code skills for training (https://docs.fireworks.ai/fine-tuning/agent/evaluators.md); you may install them.

## Phases (do them in this order; write RESULTS.md incrementally so partial work is visible)

1. **Task spec** (`SPEC.md`): one-line task, input → output, scoring rule (exact, execution-based, or field F1), who pays for it, workload assumption for the business model.
2. **Data** (`data/`): download or synthesize. `test.jsonl` locked first (rule 5), then `train.jsonl` (200 to 500 rows). Record source, license, and any synthetic-generation prompt. Synthetic labels made by a model must be made by a *different* model than any you evaluate, and say so.
3. **Scorer** (`score.py`): deterministic, unit-tested on 5 hand-written cases (include a wrong answer that must score 0). Guardrail: normalize messy outputs, count invalid outputs separately.
4. **Baseline sweep** (`results/`): all six models above (kimi-k3 on 100 rows max), plain prompt, 1 seed. Record accuracy, invalid rate, p50/p95 latency, cost per 1k. Copy and adapt `hackathon/eval/run_eval.py` and `compare.py`; keep the JSON output shape.
5. **Harness interventions**: (a) rubric prompt with rules learned from baseline misses, (b) 5-shot prompt, (c) structured output / JSON mode if the API supports it, (d) routing: small model answers; escalate to the large model when the small model's answer is invalid or low-confidence; sweep at least 3 thresholds. Measure each.
6. **Variance**: best small-model configuration and baseline re-run with 3 seeds (temperature 0 but shuffled order / different seeds); report mean ± range.
7. **Fine-tuning** (only if your brief grants SFT budget, or training is confirmed free): format `train.jsonl` into Fireworks `messages` JSONL, run `check_leak.py`, submit the job, poll until done. If the result can be scored without a dedicated deployment (serverless LoRA serving or the training API's sampling), score it on the full test set. Otherwise rule 3 applies.
8. **Chart** (`frontier.png`): x = cost per 1k requests (log), y = accuracy; one point per configuration; label the best small-model point. Use matplotlib (installed for python3.10).
9. **Business model** (`BUSINESS.md`): workload assumption (calls/day), monthly cost per configuration, errors per month per configuration, the one-sentence value claim.
10. **Pitch** (`PITCH.md`): 3-minute script following `hackathon/PLAYBOOK.md` section 4, with real numbers, plus the four slide titles and contents.
11. **README.md**: how to reproduce every number in RESULTS.md with commands.

## RESULTS.md format (the judge parses this)

```
# <task>
Status: complete | partial (what's missing)
Test set: N rows, sha256 <hash>, source <url or "synthetic">
Leak check: <paste check_leak output>
Spend: $X.XX inference, $Y.YY training (from ledger.csv)

## Results table
| config | model | accuracy | invalid | p50 s | p95 s | $/1k | seeds |
...

## Best small-model result vs. frontier
<two sentences with numbers>

## Headroom verdict
<Is this a task where the frontier model struggles? What is the gap between best small config and frontier? Would you pick this task for the real hackathon? Why?>

## Misses analysis
<5 to 10 representative failures of the best config, with a hypothesis each>

## Gotchas hit tonight
<every error, rate limit, format surprise, with the fix>
```

## When done

Finish with a final message that states: status, test-set hash, spend, the best small-model accuracy vs. frontier accuracy, and the headroom verdict in one sentence. Then stop. Do not start new work after the final message.
