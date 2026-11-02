# code-fix
Status: complete (phase 7 skipped: no SFT budget; the only free path, Muse Glimmer 30B SFT, is documented and prepared in `sft/` but not run, see DECISIONS.md item 9)
Test set: 164 rows, sha256 2bc0883f6eecfbed, source https://huggingface.co/datasets/bigcode/humanevalpack (python config = HumanEvalFix: human-written `buggy_solution` + hidden `test`)
Leak check:
```
test set: 164 rows, sha256 2bc0883f6eecfbed
data/train.jsonl: 300 rows, 0 overlap with test
data/train_messages.jsonl: 300 rows, 0 overlap with test
```
Spend: $1.96 inference, $0.00 training (from ledger.csv: 2,249 calls; glm-5p3 $0.82, glm-5p3-flash $0.44, kimi-k3 $0.38, deepseek $0.17, nemotron $0.10, gpt-oss $0.05)

## Results table
Clean numbers: rows that failed for infrastructure reasons (HTTP 429 after 5 retries, or reasoning that exhausted
max_tokens) were re-run once with max_tokens 8192 (`patch_rows.py`, DECISIONS item 10). Rows still truncated at 8192
remain invalid. The as-run table is in the appendix. kimi-k3 is on the first 100 rows (cost cap); on those same 100
rows glm-5p3-flash plain scores 100/100, glm-5p3 98/100, deepseek 95/100.

| config | model | accuracy | invalid | p50 s | p95 s | $/1k | seeds |
|---|---|---|---|---|---|---|---|
| plain | nemotron-lightning-3p5-30b-a3b | 79.3% | 17 | 3.98 | 22.30 | 0.476 | 1 |
| plain | gpt-oss-120b | 79.9% | 0 | 1.33 | 3.54 | 0.295 | 1 |
| plain | deepseek-v4p1-flash | 96.3% | 2 | 2.25 | 10.89 | 0.789 | 1 |
| plain | glm-5p3-flash | 100.0% | 0 | 2.00 | 7.43 | 0.255 | 1 |
| **plain** | **glm-5p3-flash** | **99.4% (98.8–100.0)** | 0.7 | 2.10 | 7.42 | 0.259 | **3** |
| plain | glm-5p3 (large) | 96.3% | 5 | 4.20 | 18.80 | 4.206 | 1 |
| plain, 100 rows | kimi-k3 (frontier) | 99.0% | 0 | 2.47 | 7.91 | 3.710 | 1 |
| rubric prompt | glm-5p3-flash | 98.8% | 0 | 1.90 | 7.48 | 0.260 | 1 |
| 5-shot (MBPP mutants) | glm-5p3-flash | 98.8% | 1 | 1.46 | 5.01 | 0.275 | 1 |
| 5-shot | glm-5p3-flash | 98.0% (97.0–98.8) | 1 | 1.46 | 4.91 | 0.282 | 3 |
| JSON mode (as scored) | glm-5p3-flash | 32.9% | 110 | 2.28 | 9.19 | 0.257 | 1 |
| JSON mode (re-scored, fence inside JSON unwrapped) | glm-5p3-flash | 96.3% | 5 | 2.28 | 9.19 | 0.257 | 1 |
| plain + self-confidence line | glm-5p3-flash | 98.8% | 0 | 2.58 | 9.83 | 0.332 | 1 |
| route: verify visible assert → glm-5p3 (3.0% escalated) | glm-5p3-flash→glm-5p3 | 100.0% | 0 | 2.00 | 7.75 | 0.370 | 1 |
| route: self-confidence < 50 / 70 (0% escalated) | glm-5p3-flash→glm-5p3 | 98.8% | 0 | 2.58 | 9.83 | 0.332 | 1 |
| route: self-confidence < 90 (0.6% escalated) | glm-5p3-flash→glm-5p3 | 98.8% | 1 | 2.58 | 9.83 | 0.553 | 1 |
| route: completion tokens > 1200 (5.5% escalated) | glm-5p3-flash→glm-5p3 | 99.4% | 1 | 2.00 | 9.70 | 0.891 | 1 |
| route: completion tokens > 600 (23% escalated) | glm-5p3-flash→glm-5p3 | 97.6% | 4 | 2.00 | 21.64 | 2.211 | 1 |
| route: completion tokens > 300 (49% escalated) | glm-5p3-flash→glm-5p3 | 97.0% | 5 | 2.15 | 25.04 | 3.619 | 1 |

Latency is wall-clock per request with 4 concurrent workers while nine other agents hammered the same account, so
p95 is pessimistic. $/1k is token-based from the protocol price table.

## Best small-model result vs. frontier
glm-5p3-flash with the plain one-paragraph prompt passes the hidden tests on 99.4% of problems (3 seeds, range
98.8–100%) at $0.26 per 1k requests and 2.1 s p50; kimi-k3 passes 99.0% on its 100-row subset at $3.71 per 1k and
2.5 s p50, and on those same 100 rows glm-5p3-flash is 100/100. The small model matches the frontier at 1/14 of the
cost with zero prompt engineering, and the only routing that helps (re-run the visible assert, escalate on failure)
lifts a single seed from 100% to 100% while costing 45% more.

## Headroom verdict
No. The frontier does not struggle: kimi-k3 misses 1 of 100 and the misses of every strong model are the same two or
three problems (`decode_cyclic`, `solve`, `sum_squares`). The gap between the best small config and the frontier is
+0.4 points in the small model's favour, inside seed noise (±0.6). Interventions could not move the number because
there was nothing to move: rubric and 5-shot were −0.6 to −1.4 points, JSON mode hurt (format fights the model's
fences), self-reported confidence is always 95-99 and so useless as a routing signal. I would not pick this task for
the real hackathon: the judges want "small tuned model matches frontier at 10x lower cost" and here the untuned
$0.15/M model already does, so there is no story about training, routing or harness design to tell, and no way to
show "how far we pushed it" as a curve. Two models do have headroom (gpt-oss-120b 79.9%, nemotron 79.3%), but their
misses are mostly reasoning-budget exhaustion and verbosity, not code understanding, and fixing that is a
max_tokens knob, not a hackathon.

If a code-repair task is wanted anyway, make it harder than single-function HumanEvalFix: multi-file or
repository-level bugs (SWE-bench Lite style), bugs without any failing-test output, or "fix without changing
behaviour on an adversarial hidden suite", and expect to spend the budget on a frontier-model baseline that is
actually below 80%.

## Misses analysis
Best config = glm-5p3-flash plain; across all 8 clean glm-5p3-flash runs (3 plain seeds, 3 five-shot seeds, rubric,
confidence) only 8 distinct problems ever failed:

1. **Python-142 `sum_squares`** (missing logic; invalid in 4/8 runs, `finish_reason=length` at 8192). The fix adds an
   `i % 4 == 0 and i % 3 != 0` branch that is not inferable from the one visible assert, so the model reasons in
   circles for 8k tokens and never emits code. Hypothesis: under-specified spec; the docstring variant would be easy.
2. **Python-84 `solve`** (operator misuse; wrong in 4/8). Buggy code takes the last digit instead of the digit sum. The
   visible assert `solve(1000) == "1"` is consistent with both readings; the model picks a different wrong one.
   Hypothesis: the single assert is genuinely ambiguous.
3. **Python-31 `is_prime`** (2/8): fix `is_prime(1) == False` but keep the off-by-one on the loop bound; passes the
   shown assert, fails `is_prime(4)`. Hypothesis: patching the symptom not the cause (rubric rule 1 exists for this).
4. **Python-63 `fibfib`** (2/8): base cases `fibfib(1)==0` are fixed but the recurrence stays wrong.
5. **Python-38 `decode_cyclic`** (2/8; also kimi-k3's only miss and a deepseek miss): the fix needs to understand
   `encode_cyclic`, which is not shown; the model rewrites the function and breaks a different case.
6. **Python-141 `file_name_check`** (1/8, length): many simultaneous conditions, model over-thinks.
7. **Python-134 `check_if_last_char_is_a_letter`** (1/8): `split(' ')` vs `split()`, whitespace-edge semantics.
8. **Python-87 `get_row`** (1/8): sort-order fix applied to the wrong key.

Pattern: every real miss is a problem where the one visible assert admits more than one fix. The verify router
escalated exactly 5 rows (`Python-1, 32, 38, 50, 87`) and glm-5p3 fixed all 5, which is why it reaches 100%.

## Gotchas hit tonight
- **Fireworks account suspended (HTTP 412 PRECONDITION_FAILED, "monthly spending limit")** at 22:04, 8 minutes into
  paid calls. Account-level, not a 429: backoff cannot help. `wait_and_run.sh` probed every 5 min and auto-launched the
  sweep when the account returned at 22:17 (13 minutes of downtime).
- **HTTP 429 that outlives 5 retries** (62 s of backoff) with ten agents on one account: 5-17 rows per run returned
  empty and were counted invalid in the as-run sweep. Fix: `patch_rows.py` re-ran only those rows with 2 workers and
  20/40/60 s sleeps. Lesson: log `api_error` per row and separate it from model invalidity.
- **`finish_reason=length` with empty content**: all six models reason by default; nemotron used all 4096 tokens on
  28/164 rows and still 17 at 8192; glm-5p3 (the large model!) still 5/164 at 8192. Fix: report it as invalid but
  explain it; a `reasoning_effort` knob was not tested.
- **JSON mode puts a ```python fence inside the JSON string.** Scorer took the value verbatim → SyntaxError → 32.9%.
  Fixed the extractor and re-scored offline (96.3%). Kept both numbers.
- **Self-reported confidence is useless**: 160/164 answers say 95-99 regardless of correctness, so every threshold
  below 100 escalates ~0% and 100 escalates everything.
- Hugging Face: HumanEvalPack is parquet-only and python3.10 here has no pyarrow; the datasets-server `/rows` JSON API
  worked for 2 pages then rate-limited (429 HTML). MBPP came from the Google Research GitHub mirror instead.
- `sandbox-exec` (deprecated by Apple) still works and blocks the network; my socket-monkeypatch fallback broke
  `import ssl` inside the sandbox, so it is only used when `sandbox-exec` is absent.
- HumanEvalFix tracebacks carry temp-file paths and shifted line numbers; the prompt builder strips `File ...` frames.

## Appendix: as-run table (before the infrastructure retry pass)
| config | model | accuracy | invalid | p50 s | p95 s | $/1k | seeds |
|---|---|---|---|---|---|---|---|
| plain | nemotron-lightning-3p5-30b-a3b | 64.0% | 45 | 4.09 | 11.67 | 0.345 | 1 |
| plain | gpt-oss-120b | 71.3% | 18 | 1.37 | 3.60 | 0.265 | 1 |
| plain | deepseek-v4p1-flash | 86.0% | 19 | 2.25 | 12.11 | 0.671 | 1 |
| plain | glm-5p3-flash | 93.3% | 11 | 2.01 | 10.58 | 0.254 | 1 |
| plain | glm-5p3-flash | 95.1% (93.3–96.3) | 7.7 | 2.11 | 10.23 | 0.251 | 3 |
| plain | glm-5p3 | 88.4% | 18 | 4.19 | 17.55 | 2.957 | 1 |
| plain, 100 rows | kimi-k3 | 95.0% | 4 | 2.43 | 7.08 | 3.520 | 1 |
| rubric | glm-5p3-flash | 96.3% | 6 | 1.91 | 9.24 | 0.256 | 1 |
| 5-shot | glm-5p3-flash | 98.8% | 1 | 1.46 | 5.01 | 0.256 | 1 |
| 5-shot | glm-5p3-flash | 96.1% (92.1–98.8) | 4.7 | 1.46 | 4.91 | 0.253 | 3 |
| confidence | glm-5p3-flash | 94.5% | 8 | 2.58 | 10.69 | 0.316 | 1 |
| route verify (9.2% escalated) | glm-5p3-flash→glm-5p3 | 98.2% | 3 | 2.04 | 10.58 | 0.618 | 1 |
| route tokens>1200 (10.4% escalated) | glm-5p3-flash→glm-5p3 | 97.0% | 5 | 2.00 | 13.76 | 0.738 | 1 |
Full per-row data: `results/*.json` (originals) and `results/*_retry.json` (clean). Probe files in `results/probe/`.
