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

Language in, checkable answer out.

| Task | Small, open | Frontier |
|---|---|---|
| **Cypher** | **48** | **47** |
| Clauses | 69 | 74 |
| Products | 77 | 70 |
| Intent | 87 | 88 |
| Functions | 92 | 92 |
| Tools | 98 | 95 |
| Code | 99 | 96 |

Frontier models nail the rest. **Cypher is where they break.**

<!-- Footnotes: Small, open = GLM 5.3 Flash. Frontier = Claude Opus 5 (Cypher), Kimi K3 (Clauses, Intent, Tools), GLM 5.3 (Products, Functions, Code). Also tested without a frontier run: Regex 68, Action items 93. SQL and ICD-10 not finished. Accuracy on held-out sets. -->

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
- **RFT backfired.** −8 points. It trained only on answers it already got right.
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
