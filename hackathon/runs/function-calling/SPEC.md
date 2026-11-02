# Task spec: function calling (tool selection + argument filling)

**One line.** Given a user request and a list of tool definitions (OpenAI function schema), output the one correct tool call: function name plus arguments.

**Input → output.**
- Input: `messages` (the user request, occasionally with a short system message) and `tools` (1 to 12 OpenAI-format function schemas, average 2.4).
- Output: one call `{"name": "<tool>", "arguments": {...}}`. Measured two ways: the API's native `tools` parameter (call read from `tool_calls`) and a plain-prompt JSON variant (tools rendered as JSON in the system prompt, call parsed from the text).

**Scoring (score.py, deterministic, unit-tested).**
- Gold = BFCL `possible_answer`: for each argument a list of acceptable values; `""` in the list means the argument may be omitted.
- Normalization: lowercase keys, sorted keys, numeric equality (5 == 5.0 == "5"), whitespace-stripped case-insensitive strings, ordered element-wise lists, recursive dicts. Tool names compare case-insensitively with `.` treated as `_` (the tool API forbids dots).
- `strict` = 1 only if the name is right, every required argument is present and acceptable, and there are no extra arguments. `partial` = 1 if strict, 0.5 if only the name is right, else 0. Unparseable output = `invalid`, scores 0 on both and is counted separately.
- Headline metric: strict accuracy. Partial is reported alongside.

**Data.** Berkeley Function Calling Leaderboard v4 (`ShishirPatil/gorilla`, `berkeley-function-call-leaderboard/bfcl_eval/data`, Apache-2.0), categories simple_python, multiple, live_simple, live_multiple (the last two are user-contributed real-world schemas). Test: 200 rows (40/50/40/70), locked. Train: 394 rows from the remaining pool, zero overlap with test on user text. Rows over 8,000 characters of tools+messages were dropped (37-tool catalogs that dominate cost); 3 rows with empty acceptable lists were dropped.

**Who pays.** Any product with an LLM agent that calls internal APIs: customer-support automation, booking/ordering assistants, developer-tool copilots. A wrong tool or wrong argument is a failed action the user has to redo, or worse, an action against the wrong record. Teams pay today by routing every call to a frontier model.

**Workload assumption for BUSINESS.md.** 1,000,000 tool calls/day (a mid-size agent product: ~200k daily active sessions × 5 tool calls), ~900 input tokens and ~150 output tokens per call.
