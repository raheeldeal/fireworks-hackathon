# meeting-actions (meeting transcript -> action items JSON)
Status: complete, except phase 7 not run (SDK install not permitted in this session; training itself is confirmed free, see DECISIONS.md and README.md)
Test set: 150 rows, sha256 6143b59c7fc675b7aa266e42428cd6a9a2ea231406c89d9e4dc6e2aa1d304cd4, source synthetic (gold-first: labels sampled by scripts/gen_data.py seed 2026, prose written by glm-5p3 with reasoning_effort=low; 397 generated, 150 test / 247 train)
Leak check:
```
test set: 150 rows, sha256 6143b59c7fc675b7
data/train.jsonl: 247 rows, 0 overlap with test
test set: 150 rows, sha256 6143b59c7fc675b7
data/sft_train.jsonl: 247 rows, 0 overlap with test
```
Spend: $2.70 inference ($1.36 of it data generation; ledger.csv, 2885 calls), $0.00 training

Accuracy = item-level F1 (predicted item matches a gold item when owner matches and task token-set ratio >= 0.6; one-to-one). "due acc" = exact normalized due-date match on matched items. Invalid = output not parseable as a JSON array of objects. p50/p95 are wall-clock seconds per call at 6 concurrent workers. $/1k from token counts × the PROTOCOL.md price table. Routing/filter rows are computed offline from cached per-row outputs of the two models (cost and latency summed on escalated rows).

## Results table
<!-- TABLE -->
| config | model | accuracy (item F1) | P / R | due acc | invalid | p50 s | p95 s | $/1k | seeds |
|---|---|---|---|---|---|---|---|---|---|
| baseline plain prompt | nemotron-lightning-3p5-30b-a3b | 0.921 | 0.892 / 0.951 | 0.911 | 0 | 0.56 | 1.98 | 0.063 | 1 |
| rubric prompt (n=149) | nemotron-lightning-3p5-30b-a3b | 0.899 | 0.896 / 0.901 | 0.975 | 0 | 0.56 | 1.47 | 0.076 | 1 |
| baseline plain prompt | glm-5p3-flash | 0.935 ± 0.002 | 0.903 / 0.976 | 0.983 | 0 | 1.04 | 1.46 | 0.170 | 4 |
| rubric prompt | glm-5p3-flash | 0.920 | 0.891 / 0.951 | 0.972 | 0 | 1.17 | 2.25 | 0.217 | 1 |
| rubric + JSON mode | glm-5p3-flash | 0.929 | 0.900 / 0.961 | 0.977 | 0 | 1.23 | 1.95 | 0.222 | 1 |
| rubric + confidence (n=149) | glm-5p3-flash | 0.926 | 0.893 / 0.962 | 0.974 | 0 | 1.32 | 2.25 | 0.236 | 1 |
| rubric + 5-shot | glm-5p3-flash | 0.962 ± 0.001 | 0.942 / 0.981 | 0.981 | 0 | 1.08 | 1.88 | 0.744 | 3 |
| baseline plain prompt | gpt-oss-120b | 0.936 | 0.901 / 0.974 | 0.932 | 0 | 1.17 | 1.79 | 0.280 | 1 |
| baseline plain prompt | deepseek-v4p1-flash | 0.965 | 0.951 / 0.979 | 0.985 | 0 | 1.31 | 2.34 | 0.368 | 1 |
| baseline plain prompt (n=149) | glm-5p3 | 0.930 | 0.888 / 0.975 | 0.969 | 0 | 1.36 | 1.85 | 1.556 | 1 |
| baseline plain prompt (n=70) | kimi-k3 | 0.953 | 0.924 / 0.984 | 0.963 | 0 | 2.85 | 4.18 | 5.326 | 1 |
| routing glm-5p3-flash->deepseek-v4p1-flash thr=0.01 (n=149) | route(glm-5p3-flash->deepseek-v4p1-flash) | 0.926 | 0.893 / 0.962 | 0.974 | 0 | 1.32 | 2.25 | 0.236 | 1 |
| routing glm-5p3-flash->deepseek-v4p1-flash thr=0.9 (n=149) | route(glm-5p3-flash->deepseek-v4p1-flash) | 0.946 | 0.926 / 0.968 | 0.979 | 0 | 1.37 | 3.46 | 0.292 | 1 |
| routing glm-5p3-flash->glm-5p3 thr=0.9 (n=149) | route(glm-5p3-flash->glm-5p3) | 0.930 | 0.899 / 0.964 | 0.978 | 0 | 1.37 | 3.79 | 0.479 | 1 |
| routing glm-5p3-flash->deepseek-v4p1-flash thr=0.95 (n=149) | route(glm-5p3-flash->deepseek-v4p1-flash) | 0.957 | 0.943 / 0.972 | 0.984 | 0 | 2.38 | 4.05 | 0.458 | 1 |
| routing glm-5p3-flash->glm-5p3 thr=0.95 (n=149) | route(glm-5p3-flash->glm-5p3) | 0.932 | 0.898 / 0.968 | 0.975 | 0 | 2.49 | 3.94 | 1.167 | 1 |
| v3_rubric_conf_thr0.85 (n=149) | filter(glm-5p3-flash) | 0.935 | 0.910 / 0.962 | 0.974 | 0 | 1.32 | 2.25 | 0.236 | 1 |
| v3_rubric_conf_thr0.95 (n=149) | filter(glm-5p3-flash) | 0.864 | 0.954 / 0.790 | 0.981 | 0 | 1.32 | 2.25 | 0.236 | 1 |
<!-- /TABLE -->

Variance (phase 6): <!-- VARIANCE -->glm-5p3-flash plain: 0.935 ± 0.002 over 4 runs (0.938, 0.935, 0.934, 0.935); glm-5p3-flash rubric + 5-shot: 0.962 ± 0.001 over 3 runs (0.961, 0.963, 0.962).<!-- /VARIANCE -->

Scorer sensitivity (plain prompt, F1 at task-match threshold 0.45 / 0.6 / 0.75): deepseek 0.983 / 0.965 / 0.907; kimi 0.965 / 0.953 / 0.910; glm-5p3-flash 0.958 / 0.938 / 0.878; gpt-oss 0.954 / 0.936 / 0.874; nemotron 0.946 / 0.921 / 0.859; glm-5p3 0.944 / 0.930 / 0.874. The ranking does not change with the threshold.

## Best small-model result vs. frontier
Best small configuration is glm-5p3-flash with the rubric plus five worked examples from the train split: F1 0.961 (0.962 mean over 3 runs), precision 0.942, recall 0.981, 0 invalid, p50 1.1 s, $0.74 per 1k meetings; the frontier model kimi-k3 with the plain prompt scores F1 0.953 on 70 rows at p50 2.9 s and $5.33 per 1k. The small model is 0.8 F1 points better, 2.6x faster and 7x cheaper, and the medium model deepseek-v4p1-flash (plain prompt, F1 0.965, $0.37 per 1k) beats both.

## Headroom verdict
No. The frontier model does not struggle on this task: every one of the six models scores F1 0.92 to 0.97 with zero invalid outputs on the plain prompt, and the whole field sits within about 4 points. The best small config is already *above* the frontier model, and the gap between the best small config and the best model of any size is 0.4 points, which is inside the label-noise band: the misses audit below shows that roughly 2 to 3 F1 points of every model's remaining error are commitments the transcript writer added beyond the sampled labels, or paraphrases that the 0.6 task matcher rejects. The only interventions that moved the needle were few-shot examples (+2.3) and swapping to deepseek (+2.7); the rubric prompt, JSON mode and confidence routing did nothing or hurt. There is nothing left for fine-tuning to win, and a "small beats frontier" pitch here would be a story about a saturated benchmark, not about the platform. I would not pick this task for the real hackathon. The business story (frontier premium buys nothing; $7.4k/month saved) is real but the demo would show a flat curve. If the team wants a meeting-notes task anyway, the harder version is the distractor-heavy one: raise distractors to 4 to 6 per transcript, add owner hand-offs ("can you take that? no, give it to Sam"), and drop the rule that the writer must use the due phrase verbatim, then re-measure; tonight's data shows precision (0.89 to 0.95) is the axis with any room.

## Misses analysis
Best config = glm-5p3-flash + rubric + 5-shot (seed 0): 32 false positives, 10 false negatives, 13 due mismatches out of 536 gold items. Full audit material in results/noise_audit_fewshot.txt (every unexplained false positive with the owner's transcript lines).

1. **Writer-added commitment (label noise), ma-0043:** predicted Omar "ship the config change before the deploy freeze, Thursday EOD"; the transcript has Omar saying "I'll make sure the config change goes out before then" but the sampled gold has no such item. The generator ignored "no one else agrees to do anything". Hypothesis: glm-5p3 adds small realistic commitments to make dialogue flow; about 11 of the 26 unexplained extras are of this kind. Counts against precision for every model equally.
2. **Writer-added commitment, ma-0042:** Elena "send the updated agenda, this afternoon": real line in the transcript, not in gold. Same cause; also adds a due date not on the sampled list.
3. **Paraphrase rejected by the matcher, ma-0011:** predicted Noah "fix the dashboard conversion numbers" vs gold "fix the metrics dashboard for the pipeline review"; token-set ratio < 0.6 so it counts as one FP and one FN. Hypothesis: the writer paraphrased the task heavily ("get the dashboard sorted out") and the model echoed the paraphrase. About 8 of the 26 extras are this; the F1@0.45 column shows the effect (+2 points for everyone).
4. **Paraphrase, ma-0098:** Raj "pull together an FAQ based on the survey responses" vs gold "circulate the FAQ for the customer survey": verb synonym ("circulate" vs "send around") plus reordering.
5. **Owner mis-attribution in the data, ma-0095:** gold says Chloe prepares the metrics dashboard for the pricing page; the transcript has Nadia saying "I'll prepare the metrics dashboard for the pricing page, ready by Wednesday". The writer swapped the owner. Every model "fails" this row.
6. **Genuine model error, "done" distractor, ma-0006 / ma-0035:** Tom "fill out the office move survey" and Sofia "handle final edits and visuals for the launch blog post" were reported as already finished; the model still listed them. 2 of 32 FPs. The rubric prompt was meant to fix this and did not.
7. **Genuine model error, explicit "no action needed", ma-0089:** Victor says "I'll circulate the recordings separately, no action needed from anyone" and the model extracted it. Arguably a commitment; the gold excludes it. The ambiguity is in the data design.
8. **Genuine model error, question mistaken for commitment, ma-0102:** Olivia asks "has anyone confirmed with facilities about the network drops?" and the model assigned it to her as a task. This is the open-question distractor working as intended.
9. **Due-date detail dropped, ma-0045 / ma-0075 / ma-0085:** gold "before the launch on the 9th", predicted "the 9th". The matcher's normalization strips leading "before" but not the context clause; 3 of 13 due misses. Fair to all models; a looser due matcher would remove them.
10. **Invented due date, ma-0097 / ma-0108:** gold null, predicted "today" / "today or tomorrow" from phrases like "I'll do it right after this". Hypothesis: the model treats any temporal phrase as a deadline; the rubric rule 9 did not stop it.

Breakdown of the 32 false positives: ~11 writer-added real commitments (label noise), ~9 gold paraphrases rejected at 0.6, ~2 distractor "done" items, ~3 questions/vague remarks taken as commitments, ~7 ambiguous. Implied ceiling under this scorer and data: about F1 0.98.

## Gotchas hit tonight
- **Account suspended (HTTP 412 PRECONDITION_FAILED) 22:04 to 22:22** on every model and on the billing API, after ~$1.9 total across the ten runs' ledgers ("monthly spending limit"). Not a 429; retries do not help. Fix was on the billing page (user). Generation stopped at 175/400 and resumed from where it stopped (`gen_data.py` skips ids already in data/all.jsonl); the test set was locked from the first 175 before the resume and did not change.
- **Reasoning tokens eat the whole budget and return empty content.** With max_tokens 1024: nemotron, deepseek-v4p1-flash and kimi-k3 returned `content: ""` with 1024 reasoning tokens. Fix per model (run_eval.py MODEL_EXTRA): nemotron and deepseek `reasoning_effort: "none"` (with `"low"` they still spend all 1024 tokens thinking); gpt-oss-120b `"low"` (`"none"` is HTTP 400); glm-5p3 and glm-5p3-flash `"low"` (`"none"` is HTTP 400 "thinking-only model"; default spends ~150 hidden tokens at $4.40/M on glm-5p3); kimi-k3 `"low"` (~50 reasoning tokens).
- **JSON mode `{"type":"json_object"}` collapsed the array to a single object** on glm-5p3-flash (148/148 outputs were one item). Fix: pass a `schema` with an `action_items` array inside an object and say so in the prompt. The broken run is in results/old/.
- **Rubric prompt hurt** (glm-5p3-flash 0.938 -> 0.920, nemotron 0.921 -> 0.899): exclusion rules lowered recall more than they raised precision. Few-shot (+2.3) worked; rules did not.
- **Transient errors under 10-agent load:** 1 to 8 rows per run failed after 5 retries (timeouts / 5xx). `scripts/fill_missing.py` re-runs only the missing rows and recomputes the summary; all small/medium runs are at n=150. glm-5p3 is at n=149 and kimi at n=70 by design (budget).
- **Generation ran long:** pilot transcripts were 500 to 585 words at a "300 to 500" target; target lowered to 300 to 450 (median 467 words). 3 of 400 generations failed and were not retried (397 rows).
- **Label noise from the generator:** despite "no one else agrees to do anything", glm-5p3 added small commitments in roughly 7% of transcripts and once swapped an owner. Quantified above; not corrected, because the test set is locked.
- **Due normalization:** "the end of the quarter" vs "end of quarter" was a miss; fixed at 23:20 by dropping "the"/"of", all cached runs re-scored offline (F1 unchanged, due accuracy +0 to +0.01).
- **Auto-mode permission classifier** denied creating a Python 3.11 venv and installing the Fireworks cookbook / `fireworks-ai` SDK (external code), so the free Muse Glimmer 30B LoRA SFT (promotional $0 until 2026-11-30 per docs and the starter script) was not run. Data and commands are ready (README.md).
