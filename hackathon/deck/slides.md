---
marp: true
theme: default
paginate: true
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

<!-- Notes: Graph databases today are where SQL was before BI tools. Every question needs a specialist. Fraud, compliance and supply-chain teams live on graphs. Example is the FinCEN money-transfer graph. -->

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

<!-- Footnotes: Small, open = GLM 5.3 Flash. Frontier = Claude Opus 5 (graph query), Kimi K3 (clause type, reason for contact, right tool), GLM 5.3 (product data, app command, fixed code). Why these tasks: narrow, repetitive, and checkable by code, which is where small models have a chance to win. Also tested without a frontier run: Regex 68, Action items 93. SQL and ICD-10 not finished. Accuracy on held-out sets. -->

---

# Vision

**Ask any database in plain English. Get a verified answer.**

"Top 5 actors by number of genres"

```cypher
MATCH (a:Actor)-[:ACTED_IN]->(:Movie)-[:IN_GENRE]->(g:Genre)
RETURN a.name, count(DISTINCT g) AS genres
ORDER BY genres DESC LIMIT 5
```

Run it on the database. Check the rows.

---

# Benchmark

*[Raheel adds]*

| | Claude Opus 5 | Ours |
|---|---|---|
| Accuracy | 47 | *[from benchmark]* |
| Cost / 1k questions | $9.00 | $0.77 |
| Latency, typical | 2.1 s | 1.2 s |

---

# Demo

*[30s clip: one question. Langfuse trace: query, error, repair, right rows.]*

---

# What moved the score

*[Colleague's waterfall]*

---

# What we learned

- **Price is not accuracy.** A $0.15 open model matched $9 Claude.
- **SFT was the jump.** +10 points.
- **Teach first, then reward.** RFT can only reward answers the model already finds. On hard queries it found none, so SFT beat it by 8 points.
- **The harness buys trust.** Broken queries fell from 2.2% to 0.1%.

<!-- RFT detail: rewarding only correct samples meant hard questions, which it never solved, taught it nothing. It over-reinforced easy patterns: lost 33 questions, gained 17. An earlier weighted variant had no KL penalty and collapsed to 36.5%; empty results rose from 1% to 14.5%. -->

---

# Value

**~$12k saved per analyst per year**

**$2.6B graph database market, growing ~25% a year**

Next: fine-tuned model inside the harness. Low-confidence answers go to human review.

<!-- Assumptions: 10 graph questions per analyst per week x 48 weeks = 480 a year. 20 minutes of engineer time each = 160 hours at $75/hr loaded = $12k. Market: Expert Market Research, 2025, $2.58B. Other estimates range $1.4B to $4.4B, growth 22 to 29% a year. -->

---

# Reproduce

- Code: https://github.com/raheeldeal/fireworks-hackathon
- Results: https://github.com/raheeldeal/fireworks-hackathon/blob/main/hackathon/cypher/RESULTS_FINAL.md
- Exam: https://huggingface.co/datasets/neo4j/text2cypher-2025v1
- Live graphs: https://demo.neo4jlabs.com
- Traces: *[public Langfuse trace link]*
