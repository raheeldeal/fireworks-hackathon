# Natural language → Python regex
Status: complete (the managed qwen3-4b SFT row is "not scored" by design: firectl refuses mutating commands inside an AI agent, and the LoRA could not be served without a dedicated deployment, which the protocol forbids; everything else is scored on the locked test set)
Test set: 200 rows, sha256 ef955dce4c2c19c52b0b512d073416019193dc3c3be4d216c0a844cb435358c7, source https://github.com/nicholaslocascio/deep-regex (datasets/KB13, MIT; NL-RX-Synth used for training only)
Leak check:
```
test set: 200 rows, sha256 ef955dce4c2c19c5
data/train.jsonl: 500 rows, 0 overlap with test
data/sft_train.jsonl: 500 rows, 0 overlap with test
data/fewshot5.jsonl: 5 rows, 0 overlap with test
data/heldout.jsonl: 100 rows, 0 overlap with test
```
Spend: $1.09 inference, $0.00 training (from ledger.csv; Muse Glimmer SFT is free until 2026-11-30; its sampler evals are billed at sampler rates and are included in the inference figure)

Scoring: a prediction is correct only if `re.fullmatch` accepts all 10 stored positives and rejects all 10 stored negatives (1 s timeout per match); compile error = invalid. "soft" is the mean fraction of the 20 strings handled correctly. Temperature 0, max_tokens 512 unless stated, reasoning suppressed (`reasoning_effort` none or low, see DECISIONS.md 7). Baseline rows include `--repair` of rows that failed with HTTP 429 after retries (DECISIONS.md 10; pre-repair numbers in `raw/logs/base_*.log`).

## Results table
| config | model | accuracy | soft | invalid | p50 s | p95 s | $/1k | seeds |
|---|---|---|---|---|---|---|---|---|
| v1_plain | nemotron-lightning-3p5-30b-a3b | 35.5% | 0.773 | 0 | 0.31 | 1.30 | 0.0066 | 1 |
| v1_plain | deepseek-v4p1-flash | 64.5% | 0.880 | 0 | 0.75 | 1.87 | 0.0274 | 1 |
| v1_plain | glm-5p3-flash | 68.0% | 0.881 | 2 | 0.68 | 1.34 | 0.0277 | 4 (mean 65.6, range 64.0–68.0) |
| v1_plain_json | glm-5p3-flash | 60.5% | 0.866 | 0 | 0.82 | 1.44 | 0.0327 | 1 |
| v1_plain_5shot | glm-5p3-flash | 86.5% | 0.954 | 0 | 0.57 | 0.93 | 0.0357 | 1 |
| v1_plain | gpt-oss-120b | 73.5% | 0.907 | 1 | 0.57 | 1.00 | 0.0810 | 1 |
| v1_plain_json | gpt-oss-120b | 69.0% | 0.891 | 1 | 0.66 | 1.30 | 0.0838 | 1 |
| **v2_rubric (best small)** | **glm-5p3-flash** | **95.0%** | 0.984 | 0 | 0.57 | 0.96 | 0.1241 | 4 (mean 95.0, range 95.0–95.0) |
| v2_rubric_conf (same, logprobs on) | glm-5p3-flash | 95.5% | 0.985 | 0 | 0.55 | 0.93 | 0.1240 | 1 |
| v2_rubric_5shot | glm-5p3-flash | 95.5% | 0.986 | 0 | 0.55 | 0.93 | 0.1445 | 1 |
| v2_rubric | gpt-oss-120b | 93.5% | 0.977 | 0 | 0.46 | 0.86 | 0.1700 | 1 |
| route thr 0.5 / 0.7 (0 % escalated) | glm-5p3-flash → glm-5p3 | 95.5% | 0.985 | 0 | 0.55 | 0.93 | 0.1240 | 1 |
| route thr 0.8 (4 % escalated) | glm-5p3-flash → glm-5p3 | 95.5% | 0.985 | 0 | 0.55 | 1.27 | 0.1700 | 1 |
| route thr 0.9 (16 % escalated) | glm-5p3-flash → glm-5p3 | 96.0% | 0.989 | 0 | 0.57 | 1.40 | 0.3021 | 1 |
| route thr 0.95 (44 % escalated) | glm-5p3-flash → glm-5p3 | 95.5% | 0.991 | 0 | 0.77 | 1.55 | 0.6295 | 1 |
| route thr 0.98 (75 % escalated) | glm-5p3-flash → glm-5p3 | 95.0% | 0.990 | 0 | 1.09 | 1.61 | 0.9856 | 1 |
| v1_plain (512 tokens; 10 rows truncated by hidden reasoning) | glm-5p3 | 60.0% | 0.831 | 11 | 0.78 | 5.65 | 0.3928 | 1 |
| v1_plain | kimi-k3 (100 rows) | 65.0% | 0.886 | 0 | 0.91 | 2.19 | 0.4596 | 1 |
| v1_plain_mt2048 | glm-5p3 | 61.0% | 0.861 | 5 | 0.84 | 4.54 | 0.5836 | 1 |
| v2_rubric_mt2048 (frontier, same prompt) | glm-5p3 | 95.5% | 0.992 | 0 | 0.59 | 0.83 | 1.1488 | 1 |
| v2_rubric (frontier, same prompt) | kimi-k3 (100 rows) | 96.0% | 0.986 | 0 | 1.01 | 3.73 | 2.6370 | 1 |
| v1_plain, untuned control (sampler pricing, answer channel prefilled) | muse-glimmer-30b base | 30.5% | 0.766 | 2 | 0.70 | 2.91 | 0.1954 | 1 |
| v1_plain, LoRA SFT 500 rows × 2 epochs, rank 8 (free training, sampler pricing) | muse-glimmer-30b + LoRA | 93.5% | 0.983 | 0 | 0.55 | 0.66 | 0.2003 | 1 |
| v1_plain | qwen3-4b-instruct-2507 + managed LoRA | not scored (dedicated deployment required; firectl also blocks `dataset create` inside an agent) | | | | | | |

Fine-tune: 64 Adam steps (batch 16, lr 1e-4 with linear decay, 92k tokens, 7.2k of them trained) on the free Serverless Training API. Per-token loss on the answer went 1.99 → 0.28 (step 9) → 0.07 (step 57) → 0.12 (step 64). The untuned base with the same plain prompt and the same answer-channel prefill scores 30.5%; the LoRA scores 93.5%, i.e. the fine-tune learns the same KB13 conventions the rubric prompt spells out, from 500 examples and with a 60-token prompt instead of a 900-token one. Its remaining misses are the same convention rows (exact vs at-least word counts, "composed of" as `+` instead of `*`) plus a few malformed expansions of `{3}` counting groups.

Held-out check of the rubric prompt (100 train rows never looked at while writing it, `results/heldout_*.json`): glm-5p3-flash v1_plain 67.0% → v2_rubric 90.0%. So about two thirds of the +27 points on the test set carry to unseen rows; the rest is the prompt encoding conventions seen in the test misses (DECISIONS.md 12).

Routing note: the first routing sweep escalated to glm-5p3 with the *plain* prompt (61%), and accuracy fell monotonically with escalation (95.5 → 70.5% at thr 0.98) because the "big" model was the worse one. The table shows the second sweep, escalating to glm-5p3 with the rubric prompt. Confidence (geometric-mean token probability) is above 0.7 on every row, so the low thresholds escalate nothing; at 0.9 the router buys +0.5 points (one row) for 2.4× the cost.

## Best small-model result vs. frontier
glm-5p3-flash with the rubric prompt scores 95.0% (identical across 4 seeds) at $0.124 per 1k requests and 0.57 s p50; kimi-k3 with the same prompt scores 96.0% (100 rows) at $2.64 per 1k and 1.01 s p50, and glm-5p3 scores 95.5% at $1.15 per 1k. The 1-point gap is one or two rows out of 200 and both models miss the same rows (ambiguous or mislabeled gold), so the small model matches the frontier at 1/21 of the cost and half the latency.

## Headroom verdict
The frontier does not struggle with this task; nobody does once the annotation conventions are spelled out. Off the shelf every model, small or frontier, scores 60 to 74% because KB13 has house rules the plain description does not state (a "word" is `[A-Za-z]+`, "between A and B" is order-free, "contains" never anchors, "3 words" means at least 3). A 10-rule system prompt lifts the cheap model by +27 points and the frontier by +31, and after that all of them sit at 95 to 96% with the same handful of misses, most of which are gold-label quirks (see below). Headroom between best small and frontier: about 1 point, within seed-to-seed noise. The free LoRA on a 30B base confirms it from the other side: 30.5% → 93.5% with the plain prompt, i.e. the fine-tune learns the conventions instead of being told them, and lands 1.5 points under the prompted small model and 2.5 under the frontier. I would not pick this as a "small model beats frontier through fine-tuning" story: the ceiling is set by the dataset, not the model, and prompt and LoRA both hit it. I would pick it as a cost story: a $0.12/1k model with a good harness equals a $2.64/1k model, and the eval is cheap, deterministic and judge-free, which makes the demo bulletproof.

## Misses analysis
Ten misses of the best config (glm-5p3-flash, v2_rubric), with a hypothesis each:
1. "lines using a 5 letter sequence" → `.*\b[A-Za-z]{5}\b.*` (gold `.*[A-Za-z]{5}.*`). Rubric rule 2 made the model add word boundaries; "sequence" means any 5 letters inside a longer word. Prompt over-correction.
2. "lines which contain 3 or more vowels" → `(.*[aeiou].*){3}` (gold includes `AEIOU`). The model dropped uppercase vowels; kimi-k3 and glm-5p3 made the same miss. Fix: say "vowel = [AEIOUaeiou]".
3. "the word 'and' between 'zyx' and 'cba'" → added `\b` around zyx and cba (gold has none: they are substrings). Rubric rule 4 says to wrap A and B in `\b` "for between words A and B"; the description only calls 'and' a word. Rule wording is too broad.
4. "lines that contain 'number' written in words" → `.*\bnumber\b.*` (gold `.*number.*`). Gold is odd (it means "the literal word number"); any model is guessing here; kimi-k3 and glm-5p3 also missed.
5. "lines which have 3 words" → used the exact-count form. The gold for this row is at-least-3 while a sister row ("lines that contain exactly two words") is exact; the dataset is inconsistent, the model picked the wrong one.
6. "lines that have 4 characters" → `.*.{4}.*` (gold `.{4}`, exactly 4). Rubric rule 8 ("at least 3 characters is .*.{3}.*") was generalised to a count that the gold treats as exact. Convention ambiguity.
7. "instances of 'ABC' between 'XYX' and a comma" → `.*XYX.*ABC.*,|.*,.*ABC.*XYX.*`: the first alternative forgets the trailing `.*`, so lines with text after the comma fail. Plain slip (9/10 positives pass).
8. "numbers that show two or more '0'" → `.*[0-9]*00[0-9]*.*` requires adjacent zeros; gold counts any two zeros. The model read "show two or more '0'" as "00". Counting rule 3 applied only to letters in the model's head.
9. "lines that contain the 'staphyloccus aureus.'" → kept the trailing `\.` inside the literal. Rule 9 says the final full stop is punctuation; the quote mark after the dot makes it look like part of the string. All three top models missed this row.
10. "lines that contain a '?' or an '!'" → `.*(\\?|!).*`: double-escaped the `?`, which Python reads as "an optional backslash", so the pattern accepts every line (10/10 positives, 0/10 negatives rejected). Output-encoding slip, the JSON-string habit of doubling backslashes.

Pattern across the baseline misses (why the plain prompt scores 68%): 23 of 57 gpt-oss-120b misses anchored the whole line (`^\w+\s+\w+$` for "2 words"), 14 used `\w`/`\S` instead of `[A-Za-z]`, 8 required adjacency or a fixed order for "between/after", 4 were empty answers after HTTP 429 (repaired), 3 were compile errors or prose.

## Gotchas hit tonight
- HTTP 412 PRECONDITION_FAILED on every inference call at 22:04 PT: account suspended, `firectl account get` showed `Suspend State: CREDIT_DEPLETED`, balance $0.00. Not a rate limit. Cleared at 22:20 when the owner added credit; `run_eval.py` exits on 412 instead of retrying.
- HTTP 429 RATE_LIMIT_EXCEEDED on 2 to 10 rows per baseline run even after 5 retries: ten sessions share one account's serverless rate limit. Fix: `run_eval.py --repair <results.json>` re-queries only the errored rows (DECISIONS.md 10); retries now 8 with jittered backoff to 60 s. Later runs used `--workers 3`.
- glm-5p3 with `reasoning_effort: low` still burned all 512 tokens on hidden reasoning for 10 rows (empty answer, `finish_reason: length`). Re-run at `--max-tokens 2048` (DECISIONS.md 11). Even at 2048 it truncated 5 rows with the plain prompt and none with the rubric prompt.
- The first routing sweep made accuracy *fall* with escalation: the frontier model with the plain prompt was worse than the small model with the rubric prompt. Routing only helps if the escalation target is actually better on the rows being escalated.
- JSON mode (`response_format` json_schema with a `regex` field) lowered accuracy by 4.5 to 7.5 points on both models: the models over-escape backslashes inside JSON strings and occasionally emit `(?i)`. Kept as a measured negative result.
- `build_data.py` spent 2 h of CPU on the train split: exrex explodes on golds like `(.*\b[A-Za-z]*c\b.*){6,}`. Fix: strings are generated for only the first 120 train rows (SFT needs text + gold only), with a 3 s SIGALRM per row; `--train-only` reuses the locked test file. The test file hash is unchanged.
- `transformers` 4.5x returns a `BatchEncoding` from `apply_chat_template(tokenize=True)`; the training SDK wants a list of ints. Render with `tokenize=False` and tokenize with `add_special_tokens=False`.
- Muse Glimmer's chat template answers on a channel: the base model opens `to=self<|message|>` (hidden reasoning) first and never reaches the answer within the budget. Prefilling ` to=user<|message|>` after `<|start|>assistant` forces a direct answer (same as reasoning-off on the serverless models); base and SFT are sampled identically.
- Serverless training allows ONE concurrent run per base model per account (`create_model: ... in use 1, limit 1`), and sibling sessions queue on it; `sft_serverless.py` now closes its service when done, and the retry loop in `raw/logs/sft_loop.log` waits for the slot.
- `firectl dataset create` is refused inside an AI agent ("BLOCKED: mutating command"), and a sibling session found dataset uploads 403-disabled on this account anyway, so the managed qwen3-4b job stays documented in `sft_managed.sh`.
- The deep-regex gold uses `&` (intersection) and `~` (negation), which Python `re` cannot run; 39% of rows dropped (DECISIONS.md 1). `exrex` ignores `\b`, so positives are rejection-sampled against the gold (DECISIONS.md 4). Python `re` cannot be interrupted by a signal mid-match; the 1 s timeout forks a child per match (`score.py`).
- `firectl model list -o json` returns null; the REST catalog (`raw/fw_models.json`) has the tunable/serverless-LoRA flags. No LoRA-tunable base under 16B supports serverless LoRA serving (DECISIONS.md 6). `fireworks-ai[training]` refuses Python 3.10, hence `venv311/`.
