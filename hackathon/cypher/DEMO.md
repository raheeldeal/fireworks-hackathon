# Demo script (about 3 minutes)

Open `dashboard/index.html`. Every question below is in the question explorer. Pick the config named in each step, expand the question, and click its Langfuse trace link.

## 1. The bar (20 s)
The Pareto chart, cost axis. Claude Sonnet 4.6 scores 56.6% zero-shot on this dataset (published; hollow circle, cost estimated at list price).
Our cheap open model without help (R1) sits at 50.5%.

## 2. The harness checks its own work (60 s)
- **t100** (twitter), config R5: *"Which pair of users reply to each other's tweets most often?"*
  - The first query returns no rows.
  - The arrow fix reverses a relationship the schema only declares the other way, with no model call.
  - The rows come back, and they are correct.
- **t009** (movies), config R5: *"Which pair of directors has the maximal number of actors…"*
  - Muse writes invalid Cypher four times (first try plus three repairs); the trace shows each Neo4j syntax error fed back.
  - The harness escalates to Kimi K3, which gets it right on its first attempt.
  - In Langfuse you can see each attempt, each database call, the cost and latency.

Point: the harness lifts the open model from 50.5% to 56.0% at $0.0027 per question.

## 3. Training on checked answers beats the frontier (60 s)
- **t004** (movies), configs R5 vs R6: *"Find all movies with a rating above 90."*
  - R5 returns whole movie nodes.
  - R6, fine-tuned, returns the title and rating, which is what an analyst wants and what gold expects.
- **t092** (movies): *"Which persons have acted in and directed the same movie?"*
  - R6 writes the single-pattern query and returns person and movie.

Ablation ladder: SFT on 1.5k gold (R6) reaches 66.0%, and adding 9 other graphs' gold (R6bx) reaches **68.5%** (95% CI 61.8–74.5). The whole interval sits above the frontier's 56.6%, at $0.0026 per question and 1.1 s.

## 4. Honesty slide (20 s)
- **Not memorized:** on test questions with no paraphrase in training, R6 scores 65.8% and R6bx 68.8% (`contamination.py`).
- **Not eval noise:** on the 175 audited-fair questions R6bx scores 77.1%, ranked first (`validate_eval.py`).
- **Not a head-to-head:** the frontier number is published, on a different subset of the same dataset.
- **Where the gain comes from:** about half of it is learning which columns analysts expect.

## 5. Why it works (60 s, show `dashboard/why.png` and `dashboard/waterfall.png`)
- **Waterfall:** the harness takes the open model from 50.5% to 56.0% (frontier level). SFT is the one significant jump (+10.0), and other-graph data adds +2.5, for **68.5%**. RFT-style, teacher distillation, hard-example upweighting and voting were all tested and didn't help.
- **SFT vs the frontier proxy (Kimi K3, 2.8T):**
  - **t177** "top 5 discontinued products": Kimi uses `LIMIT 5` without `ORDER BY` and gets an arbitrary 5. Ours sorts by ID, which gives the exact gold rows.
  - **t097** "oldest Keanu Reeves movie": both find Johnny Mnemonic; ours also returns the year, as analysts expect.
  - **Honest flip side, t072** "actors in both Action and Romance": the big model writes the right two-pattern query and ours doesn't. Big models still win on the hardest multi-step queries (78% vs 72% on the hard tier).
- **Harness:** 34 of its 37 rescues come from the retrieved examples (output shape), and 3 from self-correction (t100 arrow fix, t009 escalation).
- **RFT-style lost to SFT:** training only on answers the model already gets right reinforces its own habits. Gold covers what it gets wrong.
- **Size:** a 30B dense model beats 743B and 2.8T MoE models after SFT on verified data.
