# SPEC: code fix

**One line:** Given a short Python function with one bug plus the output of the failing unit test, return the corrected function.

**Input:** one user message (median ~460 chars, max ~1.2k; well under 1,000 tokens) containing
1. the buggy function (imports + signature + body, no docstring), and
2. the real failing-test output (traceback tail: the assert line that failed, or "Timeout").

**Output:** the complete corrected function in one ```python block, same name and signature.

**Scoring (execution-based, deterministic):** the predicted function is written to a temp file together with the
*hidden* test suite (HumanEvalFix `test`, 5-10 asserts per problem) and run in a subprocess
(`python3 -I`, macOS `sandbox-exec` deny-network, empty env, 10 s timeout). pass = 1; assertion failure,
runtime error or timeout = 0. Missing code block, wrong/missing function name, or a syntax error = 0 and counted
as **invalid** separately. Model output is never exec'd in the harness process.

**Who pays:** engineering teams that run an AI "auto-fix on red CI" bot. Every CI failure that the bot
repairs saves a developer the context switch (industry estimates 15-30 minutes per interrupted fix); every
wrong fix that is proposed costs review time, and every bad fix that is *merged* costs far more. The model
quality that matters is pass rate on hidden tests, exactly what this eval measures.

**Workload assumption for BUSINESS.md:** a mid-size engineering org with 2,000 failing CI runs per day that
are candidates for auto-fix (≈ 60k calls/month). Fixes are only auto-merged when the visible failing test passes
after the fix; the remainder go to a human.

**Data:** test = HumanEvalFix python (bigcode/humanevalpack, 164 problems, MIT license), human-written bugs.
train = MBPP sanitized (Google Research, CC-BY-4.0) with one rule-based AST mutation per problem, verified to
fail the tests (300 rows). No model wrote any label or any bug.
