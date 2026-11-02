# DECISIONS (code-fix)

Chronological. Each entry: what was decided, why, what it affects.

1. **Test set = all 164 HumanEvalFix python rows.** Protocol asks 150-200; the dataset has exactly 164, so I use
   all of them rather than throwing any away. Locked at 21:59, sha256 2bc0883f6eecfbed.
2. **Failing-test message = the hidden suite's first failing assert, produced by actually running the buggy code.**
   This mirrors what CI shows a developer. It reveals one assert out of 5-10 hidden ones; a model that only
   patches that one case still fails the others, which is the behaviour we want to measure.
3. **No docstring in the prompt.** HumanEvalFix has a "with docs" variant that is much easier (bugs are often
   obvious from the spec). The tests-only variant is the harder, more realistic one and leaves more headroom.
4. **Training set from MBPP + rule-based AST mutations, not from HumanEval.** HumanEval canonical solutions are the
   same functions as the test set, so mutating them would leak the fix. MBPP problems are disjoint; function
   names shared with any test entry point are excluded. Mutations are deterministic Python `ast` rewrites
   (comparison swap, arithmetic swap, ±1 constant, boolean flip, and/or swap, wrong return variable, dropped last
   statement), each verified to fail the MBPP tests. No model is involved, so the "different model than any
   evaluated" rule is satisfied trivially. Known caveat: synthetic mutants are simpler than human bugs.
5. **Sandbox = subprocess + `python3 -I` + macOS `sandbox-exec` deny-network + empty env + 10 s timeout.**
   `sandbox-exec` is deprecated by Apple but present and verified to block `urlopen` on this machine. If it is
   absent, the harness falls back to a socket monkeypatch (weaker; noted).
6. **Output extraction: last ```python block containing `def`, else JSON `fixed_code`, else raw text.** Trailing
   top-level statements (model-added asserts/prints) are dropped via `ast` before running hidden tests, so a model
   is not penalised for echoing a test, but IS penalised (invalid) for syntax errors or renaming the function.
7. **max_tokens 2048 default.** Reasoning tokens count against it. nemotron hit the limit on 1 of 2 probe rows;
   the baseline sweep will use 4096 for nemotron and record the decision in RESULTS.
8. **22:04 Fireworks account suspended (HTTP 412, monthly spending limit).** Not a rate limit; retries cannot fix
   it. Reported to the parent session and the shared notes folder. Continued with every deliverable that does not
   need the API (SPEC, scorer tests, routing/variance/chart scripts, README, free-training check) and left the
   sweep scripts ready to run with one command. The API is retried every 10 minutes by `wait_and_run.sh`.
9. **Phase 7 (fine-tuning): free path exists, prepared but not run tonight.** Evidence from docs (fetched 22:10):
   - fireworks.ai/pricing: "Muse Glimmer 30B SFT is free via UI and Serverless Training API until 11/30. No credit card required."
   - docs.fireworks.ai/fine-tuning/training-api/cookbook/muse-glimmer.md: promotion "applies the promotion to LoRA SFT jobs
     started before 2026-12-01"; "RL, DPO, full-parameter training, deployments, and inference outside the training run are
     not covered"; "In-session evaluation sampling is priced separately at the published per-token rates"; "trained LoRAs
     cannot be served on serverless inference"; requires Python 3.11+ and `git clone fw-ai/cookbook && pip install -e .`.
   - docs.fireworks.ai/fine-tuning/training-api/serverless.md: "Sampling runs on the shared pool, so there's no deployment to
     create or hot-load" via `service.create_sampling_client(model_path=...)`. So a tuned checkpoint CAN be scored on the full
     test set without a dedicated deployment (rule 3 satisfied); the sampling tokens are paid at serverless rates and would
     come out of the $3 inference cap.
   Why not run: (a) the account is suspended, so the "job creation page shows no price" check (rule 4) cannot be done;
   (b) the sweep must finish first and it consumes most of the cap; (c) the 3.11 venv + cookbook install is an unattended
   risk. What is ready: `data/train_messages.jsonl` (Fireworks messages format, leak-checked) and `sft/COMMANDS.md`.
   Glimmer 30B is not one of the six benchmarked models, so its untuned baseline would also need a run (~$0.05).
10. **23:50 Retry pass for infrastructure failures (`patch_rows.py`).** In the as-run sweep, every "invalid" output was
    either an HTTP 429 that survived five retries (ten agents share one account; 5-17 rows per run) or
    `finish_reason=length` (reasoning used the whole 2048/4096 budget, content empty). Neither says anything about
    the model's ability to fix code, so I re-ran exactly those rows with max_tokens 8192, 2 workers and slower
    backoff, and wrote `*_retry.json` next to the untouched originals. RESULTS.md reports the clean numbers as the
    main table and the as-run numbers in an appendix so the judge can see both. Cost of the pass: $0.51.
    Rows that still hit `length` at 8192 (glm-5p3: 5, nemotron: 17, deepseek: 2, flash 5-shot: 1) stay invalid: a
    model that needs more than 8k tokens of thinking for a one-line fix is not usable for this task.
11. **JSON mode re-scored offline, no new calls.** glm-5p3-flash in JSON mode wrapped a fenced block inside the JSON
    string; my extractor took the JSON value verbatim and the fences caused a SyntaxError (110 invalid, 32.9%).
    Fixed `extract_code` to unwrap a fence inside the JSON value and re-scored the same raw outputs:
    `glm-5p3-flash_v1_plain_json_rescored.json` (96.3%). Both files are kept; the unit tests still pass.
12. **Routing escalates to glm-5p3, not kimi-k3.** kimi-k3 was only run on 100 rows (cost cap), and offline routing
    needs the large model's answer for every row. glm-5p3 is the large model in every routed row.
