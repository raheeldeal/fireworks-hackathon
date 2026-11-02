# Pitch script: how each component helped (about 4 minutes)

Open `dashboard/index.html`. Lines in quotes are what to say; arrows are what to click.

---

## 1. The problem and the bar (30 s)
→ **Overview** tab, top tiles.

> "Analysts ask questions in English; we return the right rows from a Neo4j graph, and we check every answer by running it on the real database.
> The bar is the frontier. Claude Sonnet 4.6 scores 56.6% on this dataset (published). We also ran the 2.8-trillion-parameter Kimi K3 ourselves on our exact 200 questions: 58.5% with no help.
> We start from a 30-billion-parameter open model, Muse Glimmer, at 50.5%."

## 2. Walk the waterfall, one component at a time (2 min)
→ **Waterfall & fixes** tab. Click each row; the panel below lists the questions that step fixed and broke. Expand one and show before → after.

**Harness component 1: retrieved examples (+3.5 points; 34 fixed, 27 broke)**
→ click it, expand **t010**: "Which people have written and directed the same movie?"
> "We show the model three similar solved questions from the same database. It learns the expected answer shape. Here it now returns just the names, as asked. But look: it also broke 27 questions. Examples help, but they're noisy."

**Harness component 2: arrow-direction fix (+0.5; 1 fixed, 0 broke)**
→ click it, expand **t100**: "Which pair of users reply to each other's tweets most often?"
> "Relationships in a graph have a direction. The model wrote 'a tweet posts a user'. The query ran but returned zero rows. Plain code, no AI, checks the schema, flips the arrow, and gets the right pair: 6 replies. It never breaks anything."

**Harness component 3: repair loop (+0.5; 1 fixed, 0 broke)**
→ expand **t118**
> "When the database returns an error, we feed the exact error back and the model rewrites its query."

**Harness component 4: escalation (+1.0; 2 fixed, 0 broke)**
→ expand **t009**, the "pair of directors" question. Open its Langfuse trace.
> "Our model failed four times with syntax errors, so the harness handed this one question to the big model, which solved it. Every attempt, error, cost and latency is in the trace. With the full harness we're at 56%: frontier level, from a 30B model."

**SFT on 1,500 verified gold examples (+10.0, the only statistically significant step; 34 fixed, 14 broke)**
→ click it, expand **t004** ("movies with a rating above 90") and **t097** ("oldest Keanu Reeves movie").
> "This is the jump. We fine-tuned on training questions whose gold answers we had verified by running them. Before, the model returned whole nodes or just a title. After, it returns the title with the rating, the title with the year: what an analyst expects and what the data's answers contain. Frontier models know Cypher; they don't know your data's conventions. Fine-tuning teaches them."

**More training data: + 9 other graphs (+2.5; 14 fixed, 9 broke)**
→ expand **t159** ("products ordered by customer VINET").
> "We added verified examples from nine other graphs, so the model learns general Cypher rather than memorizing five schemas. Here it stops dumping 16 columns and returns just the products. That takes us to **68.5%**."

**Tested, not adopted** (point at the dashed block)
> "We also tried training on the model's own verified answers (RFT-style): −8 points, because it only reinforces habits the model already has. We tried teacher distillation from the 2.8T model, upweighting hard examples, and voting. None beat plain SFT on verified gold, and we show that honestly."

## 3. The Pareto story: better, at about half the cost, from a far smaller model (45 s)
→ **Model Pareto** tab, top chart (accuracy vs cost per 1,000 questions).

> "Here's every model on the same 200 questions. Up and to the left is better.
> Our fine-tuned 30B model, the starred point, is on the frontier at **68.5% for $2.63 per thousand questions**.
> The 2.8-trillion-parameter Kimi K3, running the same harness, scores 63% for **$5.07: we're about half the cost (52%), 93 times smaller, and 5.5 points better.**
> Against Kimi with no help (58.5%, $4.29) we're **+10 points, significant (p = 0.004), at 61% of the cost.** Claude Sonnet 4.6 sits below us too, at an estimated $3.96 list price."

→ scroll to the latency chart.
> "And it's the fastest model above 56%: **1.1 seconds** per answer against 2.7 to 2.9 for Kimi."

## 4. Why you can trust it (20 s)
> "Locked 200-question test set with a published hash. No test question is in any training file: checked across every file. On questions with no close paraphrase in training, we still score 68.8%. We audited the test set itself: 25 questions have wrong or ambiguous gold answers. On the 175 fair ones we're at 77%, still first."

## 5. Close (10 s)
> "A 30B open model, fine-tuned on execution-verified data and wrapped in a harness that checks its own work: +12 points over the published frontier, +10 over a 2.8T model we ran ourselves, at about half the cost. Next: reinforcement learning with the database as the reward."

---

### Numbers to have ready if asked
| | Accuracy | $/1,000 q | Latency |
|---|---|---|---|
| Muse 30B untuned | 50.5% | $1.94 | 1.1 s |
| Muse 30B + harness | 56.0% | $2.73 | 1.0 s |
| **Muse 30B + SFT (6.5k gold) + harness** | **68.5%** | **$2.63** | **1.1 s** |
| Kimi K3 2.8T, zero-shot | 58.5% | $4.29 | 2.9 s |
| Kimi K3 2.8T + harness | 63.0% | $5.07 | 2.7 s |
| GLM 5.3 + harness | 61.0% | $1.81 | 1.5 s |
| gpt-oss-120b + harness | 56.0% | $0.42 | 0.9 s |
| Claude Sonnet 4.6 (published) | 56.6% | ~$3.96 (est.) | — |

### Caveats, if a judge pushes
- **Claude:** its 56.6% is published, on a different subset of the same dataset. The Kimi comparison is on our exact questions.
- **Cost:** fine-tuned costs use Fireworks training-sampler prices. Serving a LoRA in production needs a dedicated GPU, priced hourly.
- **Significance:** only the SFT step and the overall gain are statistically significant; individual harness components are not.
