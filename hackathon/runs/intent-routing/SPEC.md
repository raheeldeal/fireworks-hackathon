# SPEC: Banking intent routing (Banking77)

**Task in one line:** Given a short customer message to a digital bank, output exactly one of 77 fine-grained intents.

**Input → output:** `text` (one customer utterance, 1 to 2 sentences) → `intent` (one of the 77 Banking77 labels) plus an optional self-reported `confidence` in [0, 1] used only for routing.

**Scoring rule:** exact match on the normalized label (lowercase, trailing `?` stripped). Any output that is not one of the 77 labels is `invalid` and counts as wrong. Reported separately: invalid rate, p50/p95 latency, $ per 1k requests.

**Data:** Banking77 (PolyAI, CC-BY-4.0). Test = 2 utterances per intent sampled from the official test split (154 rows, locked, stratified). Train/few-shot pool = 4 per intent from the official train split (308 rows), checked for no overlap.

**Who pays:** the support operations lead at a digital bank or fintech. Each misroute costs a human re-triage (industry figures: 1 to 3 minutes of agent time) and a slower answer for the customer.

**Workload assumption for the business model:** 50,000 inbound chat/email messages per day (a mid-size neobank), every one classified once.

**The question this run answers:** with 77 fine-grained classes, (1) does the frontier open model leave headroom, and (2) can a small model plus confidence-based escalation match frontier accuracy at a fraction of the cost?
