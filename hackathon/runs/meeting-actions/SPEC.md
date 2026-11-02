# Task spec: meeting transcript -> action items

**One line:** Given a short multi-speaker meeting transcript, output the list of action items that were actually committed to, each with owner, task, and due date (or null).

**Input:** a 300 to 500 word transcript, `Name: line` format, 4 to 5 speakers.

**Output:** a JSON array. Each element: `{"owner": "<first name>", "task": "<short verb phrase>", "due": "<deadline exactly as spoken>" | null}`. Nothing else.

**Scoring (score.py):** predicted items are matched to gold items by same owner (case-insensitive) and task token-set ratio >= 0.6 (greedy, best match first, one-to-one). Report item-level precision, recall, F1 (micro over the test set), plus exact due-date accuracy on matched items (normalized: lowercase, strip punctuation and leading "by/on/before"). **Headline accuracy = item F1.** Output that is not a JSON array of objects after light cleanup (code fences stripped, first `[...]` extracted) counts as invalid and contributes zero predictions.

**Hard part:** distractors. Every transcript also contains 1 to 3 things that were discussed but not assigned (deferred ideas, rejected suggestions, completed work, open questions). Over-extraction kills precision.

**Who pays:** meeting-notes products (Granola, Otter, Fellow, Zoom AI Companion) run this on every recorded meeting. Workload assumption for BUSINESS.md: a mid-size notes product processing 50,000 meetings/day.

**Data:** fully synthetic, gold-first (see DECISIONS.md). Labels are sampled programmatically, then glm-5p3 writes a transcript containing exactly those commitments.
