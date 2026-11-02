---
marp: true
theme: default
paginate: true
---

# What is Cypher?

**It's SQL for graph databases.**

Graph databases store connections: who paid whom, who follows whom, what ships where.

- Fraud rings (FinCEN money transfers)
- Social networks (Twitter)
- Recommendations (movies)
- Supply chains (Northwind orders)

**Frontier models get Cypher right less than half the time.** Claude Opus 5: 47 out of 100.

---

# Your data is a graph.
# Your questions wait in a ticket queue.

**"Which countries received the most money from Singapore?"**

```cypher
MATCH (f:Filing) WHERE f.originator_iso = "SGP"
MATCH (f)-[:BENEFITS]->(e:Entity)-[:COUNTRY]->(c:Country)
WITH c.name AS country, count(f) AS filings
ORDER BY filings DESC RETURN country, filings LIMIT 5
```

Analyst asks. Engineer writes this. **Answer in 2 days.**

---

# Why Cypher

We tested everyday business tasks where a computer can check the answer.

| What goes in → what comes out | Kind | Small, open | Frontier |
|---|---|---|---|
| **Question → graph database query** | **Write code** | **48** | **47** |
| Contract clause → clause type | Pick a label | 69 | 74 |
| Product web page → product data form | Fill a form | 77 | 70 |
| Support ticket → reason for contact | Pick a label | 87 | 88 |
| Request → app command with settings | Fill a form | 92 | 92 |
| Request → right tool out of 100 | Pick a label | 98 | 95 |
| Broken code → fixed code | Write code | 99 | 96 |

Everywhere else, models already score 70 to 99. **Graph queries are where even frontier models fail half the time.**

<!-- Small, open = GLM 5.3 Flash. Frontier = Claude Opus 5 (graph query), Kimi K3 (clause type, reason for contact, right tool), GLM 5.3 (product data, app command, fixed code). -->

---

# Vision

**Every analyst can question their company's connections in plain English, and trust the answer in seconds.**

A small open model you own. Checked by the database itself.

---

# Benchmark

**58.5 → 68.5**

Frontier-class model → our system. Same 200 held-out questions, every query run on a live graph.

| | Frontier | Ours |
|---|---|---|
| Correct out of 100 | 58.5 | **68.5** |
| Cost per 1,000 questions | $9.00 | **$0.77** |
| Typical response time | 2.1 s | **1.2 s** |

<!-- Frontier on the 200: Kimi K3, run by us. Claude Sonnet 4.6 published 56.6 on another subset. Cost and latency: Claude Opus 5 vs our open-model harness on the same 100 questions. -->

---

# Cheaper and more accurate than the frontier

*[Image: frontier.png]*

Same 100 questions. Up and left is better.

---

# What moved the score

*[Image: waterfall.webp]*

50.5 → 68.5. Fine-tuning (SFT) gave the biggest jump: +10.

---

# Demo

*[30s clip: one question. Langfuse trace: query, error, repair, right rows.]*

---

# What we learned

- **Price is not accuracy.** A $0.24 open model beat $9 Claude.
- **SFT was the jump.** +10 points.
- **Teach first, then reward.** RFT can only reward answers the model already finds. On hard queries it found none, so SFT beat it by 8 points.
- **The harness buys trust.** Broken queries fell from 2.2% to 0.1%.

---

# Value

**~$12k saved per analyst per year**

**$2.6B graph database market, growing ~25% a year**

Next: RFT on top of the fine-tuned model. Low-confidence answers go to human review.

<!-- Assumptions: 10 graph questions per analyst per week x 48 weeks. 20 minutes of engineer time each = 160 hours at $75/hr = $12k. Market: Expert Market Research 2025, $2.58B. -->

---

# Reproduce

- Code: https://github.com/raheeldeal/fireworks-hackathon
- Results: https://github.com/raheeldeal/fireworks-hackathon/blob/main/hackathon/cypher/RESULTS_FINAL.md
- Exam: https://huggingface.co/datasets/neo4j/text2cypher-2025v1
- Live graphs: https://demo.neo4jlabs.com
- Traces: *[public Langfuse trace link]*
