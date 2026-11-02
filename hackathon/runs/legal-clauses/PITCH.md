# Pitch: legal clause classification (3 minutes)

Honest version: the fine-tune tied the best prompt. The pitch is the cost story, not an accuracy story.

**1. Problem and who pays (20 s).**
"Every contract that enters a CLM system gets its clauses tagged so lawyers can search by provision and run playbook checks. A mid-size customer tags 3.6 million clauses a month. Today that is paralegals and keyword rules, and the LLM answer costs $26k a month with the frontier model."

**2. Task and eval (20 s).**
"Input: one clause. Output: one of 100 LEDGAR categories from real SEC contracts. We locked a 199-clause test set, two per category, scored by exact match and macro-F1, three seeds for the headline rows. Nothing in training touches it; the leak check is in the repo."

**3. Baseline (20 s).**
"Off-the-shelf: nemotron 30B 57%, GLM 5.3 Flash 67%, DeepSeek Flash 69%. The big ones: GLM 5.3 66%, Kimi K3 74% at $7 per thousand calls. Every model plateaus around 70%. The frontier model is not better than a 20x cheaper model on the same 80 clauses."

**4. What we changed (40 s).** One diagram: clause -> small model -> label, with the 2,700-token label list crossed out and replaced by the fine-tuned weights.
"We tried the usual harness tricks. JSON mode: +2 points. Five-shot: 0. A rubric of 25 disambiguation rules: minus 3. Routing to a bigger model on low confidence: capped at the small model's own ceiling. Then we fine-tuned Muse Glimmer 30B with LoRA on 500 labeled clauses, five per category, 64 steps, training free on Fireworks. The prompt shrank from 2,700 tokens to 330 because the categories now live in the weights, and the model answers in 4 tokens without thinking."

**5. Result (40 s).** The table slide.
"Best prompt-only small model: 68.8% ± 0.5 at $0.36 per thousand. Frontier: 74% on 80 rows, where the small model scores 76%. Fine-tuned 30B: 68.8%, zero invalid answers, 480-token requests, 0.66 s. Same accuracy as the frontier on matched clauses, 20x cheaper, and a request one sixth the size."

**6. Business value (20 s).**
"At 3.6M clauses a month: frontier $26k, best small model $1.3k, same number of wrongly tagged clauses. Each wrong tag is a playbook check that silently passes, and no model on the board fixes that today."

**7. How far we pushed it (20 s).** The frontier chart.
"Prompting bought 2 points. Routing bought 0. Fine-tuning on 500 clauses bought 0 accuracy and 44 of its 62 misses are the same clauses the prompt misses: near-synonym headings like Indemnifications versus Indemnity, where the dataset itself is inconsistent. That is the ceiling. The honest takeaway is that this benchmark needs more examples per class or a coarser label set before anyone, frontier included, beats 75%."

## Slides
1. **Title:** "100 clause types, one small model: matching Kimi K3 on LEDGAR at 1/20th the cost." Subtitle: task, data source, test-set size and hash.
2. **Table:** config, accuracy (± range), invalid, p50, $/1k, for nemotron, GLM Flash plain and JSON, DeepSeek Flash, GLM 5.3, Kimi K3, Muse Glimmer LoRA.
3. **Diagram:** before/after request shape (2.7k-token label list + thinking vs 330-token prompt + 4-token answer) with the training loop box (500 rows, LoRA rank 8, 64 steps, free).
4. **Business value:** the 3.6M/month table with $/month and errors/month per configuration, one sentence of value claim.
