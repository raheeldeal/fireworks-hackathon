# SPEC: tool selection at scale (mcp-tool-pick)

**One line:** given a user request and a catalog of 100 MCP-style tools (name + one-line description), output the single best tool name.

**Input:** `text` (one user message, 1 to 3 sentences) plus the catalog (fixed, 100 tools, 16 servers, ~1,900 tokens as plain text).
**Output:** one tool name from the catalog, e.g. `calendar.update_event`. A ranked list (top-3) is accepted; the first valid name is the top-1 answer.

**Scoring:** top-1 exact match on the tool name (primary). Also top-3 hit rate when the model returns a ranked list. Any output containing no catalog name is `invalid` (counted separately, scores 0). Case-insensitive; surrounding punctuation, quotes, JSON wrappers and `</think>` blocks are stripped.

**Why it is hard:** the catalog has deliberately confusable neighbors within each server (create vs update vs delete event; send vs reply vs forward email; reminders.create vs calendar.create_event; fs.search_files vs drive.search_files vs github.search_code). Requests never name the tool and often avoid the catalog's verb.

**Who pays:** anyone running an agent gateway with a large tool surface (MCP hubs, enterprise copilots). Every user turn starts with "which tool?", and a wrong pick means a wrong side-effect (an email sent instead of drafted) or a wasted round-trip. The catalog is re-sent on every call, so the tokens of the catalog dominate the cost at scale.

**Workload assumption for BUSINESS.md:** 1,000,000 routing decisions per day (a mid-size copilot: 50k daily active users × 20 turns).

**Data:** synthetic. Gold tool sampled first (5 requests per tool, 5 prescribed styles), request text written by `glm-5p3` (generation prompt in `gen_data.py`). Test 180 rows (locked), train 320 rows.
