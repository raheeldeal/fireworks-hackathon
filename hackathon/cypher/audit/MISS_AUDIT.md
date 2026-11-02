# Hand audit of 40 scored-wrong rows

Run audited: `results/glm-5p3-flash_v1_plain_n200.json` (v1 strict scorer, 57.0%, 86 misses).
Rows taken: **all 36 easy-tier misses**, then the first 4 medium-tier misses (t002, t004, t008, t011)
to reach 40. Predictions were re-executed against the live graphs (`audit/exec_cache.json`), so the
full predicted row sets were compared, not the stored 5-row heads. Raw dump: `audit/miss_dump.txt`.

## Counts

| class | n | share of 40 | now correct under `score_v2` |
|---|---|---|---|
| SCORING_ARTIFACT | 20 | 50% | 5 |
| GOLD_DEFECT | 11 | 27.5% | 0 |
| AMBIGUOUS_QUESTION | 7 | 17.5% | 0 |
| REAL_ERROR | **2** | **5%** | 0 |

**The headline finding: on easy-tier misses the model is genuinely wrong 2 times in 36.** The other
34 misses are the scorer, the gold query, or the question. That is the evidence that v1 was
mis-grading - not the comparison with published 78% numbers, which are measured on other test sets.

**The second finding: v2 only recovers 5 of the 20 scoring artifacts.** The other 15 are
*projection* mismatches - the prediction returns exactly the right rows but a different set of
columns - and we deliberately did **not** write a rule for those (see `SCORING.md`). Published
execution accuracy counts the projection, and a rule that ignored it would also pass a prediction
that dropped the column holding the answer. That is a **dataset** problem (gold projections often do
not match their own question text), not a scorer problem, and it is the single biggest reason the
easy tier still scores lowest.

## Why easy < medium, and why v2 does not fix it

Easy = single hop, no aggregation. In this dataset that is not "less difficult", it is
**"less specified"**: a bare lookup where the gold author freely chose what to project
(`RETURN m` vs `RETURN m.title` vs `RETURN m.title, m.votes`) and freely invented an ordering for
"first 3". Medium and hard rows pin the projection, because the question names the aggregate
("how many", "the average", "top 5 by X") and the number must be returned. So the easy tier carries
almost all the projection and tie noise. 30 of the 36 easy misses are projection, gold, or question
problems; 2 are real errors. Of the 31 residual v2 misses on this run that return exactly gold's
rows with a different projection, the large majority are easy rows.

## Full table

v2 = verdict under `score_v2`. "dup" = gold returns the same entity several times.

| # | id | tier | class | what actually happened | v2 |
|---|---|---|---|---|---|
| 1 | t007 | easy | SCORING_ARTIFACT | Same 5 movies; gold also returns `votes`, which the question ("movies and their release years") never asked for | wrong |
| 2 | t015 | easy | GOLD_DEFECT | Gold joins `(o)-[:ORDERS]->(p)` so its "first 3 orders" is **order 10248 three times**; prediction returns 3 distinct orders | wrong |
| 3 | t018 | easy | SCORING_ARTIFACT | Identical 13 products; gold projects `(name, unitPrice)`, prediction returns the node | wrong |
| 4 | t026 | easy | GOLD_DEFECT | Gold returns 3 rows of `null, null` (Tweet nodes have no `text`/`created_at`) | wrong |
| 5 | t027 | easy | SCORING_ARTIFACT | Tie under LIMIT: dozens of users have `followers = 0`; 2 of 3 rows match, plus node-vs-projection | wrong |
| 6 | t028 | easy | SCORING_ARTIFACT | `RETURN p` vs `RETURN DISTINCT p.name`, same person | **correct** |
| 7 | t030 | easy | GOLD_DEFECT | `size(m.languages)` is `null` for the top rows, so gold's top 5 is 5 nulls | wrong |
| 8 | t032 | easy | AMBIGUOUS_QUESTION | "same release **year**": gold compares the full `released` date (`1995-11-22`), prediction compares `m.year` | wrong |
| 9 | t039 | easy | AMBIGUOUS_QUESTION | "Which tweets have the highest favorites" names no count; gold `LIMIT 1`, prediction `LIMIT 10`, top row identical | wrong |
| 10 | t050 | easy | GOLD_DEFECT | "5 most recent users who started following" - no timestamp exists on `FOLLOWS`; gold orders by `followers` instead, so gold does not answer its own question | wrong |
| 11 | t057 | easy | AMBIGUOUS_QUESTION | "released in the '90s": `m.released` (string) and `m.year` (int) disagree in the data (Pride and Prejudice: 1996 vs 1995) | wrong |
| 12 | t066 | easy | SCORING_ARTIFACT | Identical 41 titles; prediction adds `year` and `imdbRating` | wrong |
| 13 | t070 | easy | SCORING_ARTIFACT | Same 5 tweets; gold projects `(text, favorites, link_url)`, prediction returns the Tweet node | wrong |
| 14 | t071 | easy | GOLD_DEFECT | `m.imdbVotes` is `null` for the top rows, so gold's answer is 3 nulls; the prediction counts `RATED` edges, which is what the question describes | wrong |
| 15 | t072 | easy | SCORING_ARTIFACT | Same 20 products; gold returns 4 columns, prediction returns `productName` ("which products") | wrong |
| 16 | t085 | easy | GOLD_DEFECT | Gold returns 3 rows of `null, null` | wrong |
| 17 | t090 | easy | SCORING_ARTIFACT | Same 5 users in the same order; prediction omits `u.name`. (`statuses` is null for all, so the ordering is arbitrary too) | wrong |
| 18 | t091 | easy | SCORING_ARTIFACT | "What is the **title**": prediction returns the title, gold returns title **and** votes. The prediction is the better answer and is scored wrong | wrong |
| 19 | t094 | easy | GOLD_DEFECT | Gold does not aggregate, so its "top 5 movies" is top 5 *relationships* and lists Cloud Atlas 3 times | wrong |
| 20 | t101 | easy | SCORING_ARTIFACT | Same 15 movies; prediction adds a `votes` column | wrong |
| 21 | t110 | easy | AMBIGUOUS_QUESTION | "first 3" with no order given; gold invents `ORDER BY productName`, prediction takes an arbitrary 3 | wrong |
| 22 | t112 | easy | AMBIGUOUS_QUESTION | `a.bornIn = 'France'` vs `CONTAINS 'France'`; the field holds values like "Paris, France" | wrong |
| 23 | t119 | easy | AMBIGUOUS_QUESTION | "first 3" with no order; gold invents `ORDER BY ratio DESC` | wrong |
| 24 | t122 | easy | GOLD_DEFECT | Question asks for the user's **location**; gold returns the Tweet node. The prediction returns a location | wrong |
| 25 | t129 | easy | SCORING_ARTIFACT | Same 3 products in the same order; gold adds `productID`, `unitPrice` | wrong |
| 26 | t140 | easy | **REAL_ERROR** | Prediction omits `WHERE m.released IS NOT NULL`, so `ORDER BY ... DESC` puts nulls first and it returns 5 movies with no release date | wrong |
| 27 | t142 | easy | SCORING_ARTIFACT | Same 2 movies; gold projects `(title, released)`, prediction returns the node | wrong |
| 28 | t144 | easy | SCORING_ARTIFACT | `RETURN m` vs `RETURN m.title`, same movie | **correct** |
| 29 | t145 | easy | GOLD_DEFECT | Gold's top 3 entities contains Barclays **twice** (one row per filing), so it answers "3 filings" not "3 entities"; the prediction uses `DISTINCT` | wrong |
| 30 | t154 | easy | SCORING_ARTIFACT | Same 5 users in the same order; prediction omits `user.following` | wrong |
| 31 | t158 | easy | SCORING_ARTIFACT | `RETURN m` vs `RETURN m.title`, same movie | **correct** |
| 32 | t174 | easy | SCORING_ARTIFACT | Same 144 users; gold projects `(name, screen_name)`, prediction returns the node | wrong |
| 33 | t185 | easy | SCORING_ARTIFACT | Same 122 movies; prediction adds `runtime` and `imdbRating` | wrong |
| 34 | t186 | easy | **REAL_ERROR** | No null filter plus `ORDER BY abs(revenue - budget)`, so it returns 3 movies with `null` difference | wrong |
| 35 | t192 | easy | SCORING_ARTIFACT | `RETURN e` vs `RETURN e.name`, same 3 entities | **correct** |
| 36 | t199 | easy | SCORING_ARTIFACT | "List the **roles**": prediction returns the 13 role lists, gold also returns person and movie | wrong |
| 37 | t002 | medium | AMBIGUOUS_QUESTION | Two distinct `Entity` nodes are both named "Vnesheconombank"; gold groups by node (6), prediction groups by name (7). The question asks for **names** | wrong |
| 38 | t004 | medium | GOLD_DEFECT | Gold returns 2 rows of `null, null` (the retweeted originals have no text) | wrong |
| 39 | t008 | medium | GOLD_DEFECT | "List all suppliers" - gold returns 10 rows, one per product, repeating 4 suppliers; the prediction returns the 4 distinct suppliers | wrong |
| 40 | t011 | medium | SCORING_ARTIFACT | `RETURN f` vs `RETURN f.sar_id`, same single filing | **correct** |

## 10 verbatim examples

### 1. t091 - SCORING_ARTIFACT. The prediction answers the question better than gold does.
```
Q     : What is the title of the movie with the highest number of votes?
GOLD  : MATCH (m:Movie) RETURN m.title, m.votes ORDER BY m.votes DESC LIMIT 1
GOLD  : [{"m.title": "The Matrix Reloaded", "m.votes": 1951}]
PRED  : MATCH (m:Movie) RETURN m.title ORDER BY m.votes DESC LIMIT 1
PRED  : [{"m.title": "The Matrix Reloaded"}]
```

### 2. t199 - SCORING_ARTIFACT. Gold returns two columns the question did not ask for.
```
Q     : List the roles of any person in movies with a title containing 'Matrix'.
GOLD  : MATCH (p:Person)-[r:ACTED_IN]->(m:Movie) WHERE m.title CONTAINS 'Matrix'
        RETURN p.name AS person, m.title AS movie, r.roles AS roles
GOLD  : [{"movie": "The Matrix", "person": "Emil Eifrem", "roles": ["Emil"]}, ... 13 rows]
PRED  : MATCH (p:Person)-[r:ACTED_IN]->(m:Movie) WHERE m.title CONTAINS 'Matrix' RETURN r.roles
PRED  : [{"r.roles": ["Emil"]}, {"r.roles": ["Agent Smith"]}, ... 13 rows]
```

### 3. t018 - SCORING_ARTIFACT. Node vs projection, identical 13 products.
```
Q     : Display all products that are not discontinued and have a 'unitPrice' above 35.
GOLD  : MATCH (p:Product) WHERE p.discontinued = false AND p.unitPrice > 35
        RETURN p.productName, p.unitPrice
GOLD  : [{"p.productName": "Northwoods Cranberry Sauce", "p.unitPrice": 40.0}, ... 13 rows]
PRED  : MATCH (p:Product) WHERE p.discontinued = false AND p.unitPrice > 35 RETURN p
PRED  : [{"p": {"_labels": ["Product"], "unitPrice": 40.0, "productName": "Northwoods Cranberry
         Sauce", ...}}, ... 13 rows]
```

### 4. t192 - SCORING_ARTIFACT, **recovered by v2** (rule R7).
```
Q     : List the first 3 entities that are concerned in filings with an amount greater than 1000000.
GOLD  : MATCH (f:Filing)-[:CONCERNS]->(e:Entity) WHERE f.amount > 1000000 RETURN e LIMIT 3
GOLD  : [{"e": {"name": "Piraeus Bank", ...}}, {"e": {"name": "Sberbank of Russia", ...}},
         {"e": {"name": "VTB Bank", ...}}]
PRED  : MATCH (f:Filing)-[:CONCERNS]->(e:Entity) WHERE f.amount > 1000000 RETURN e.name AS entity LIMIT 3
PRED  : [{"entity": "Piraeus Bank"}, {"entity": "Sberbank of Russia"}, {"entity": "VTB Bank"}]
```

### 5. t015 - GOLD_DEFECT. Gold's "first 3 orders" is one order, three times.
```
Q     : List the first 3 orders shipped to France.
GOLD  : MATCH (o:Order)-[:ORDERS]->(p:Product) WHERE o.shipCountry = 'France'
        RETURN o.orderID, o.shipName, ... ORDER BY o.shippedDate LIMIT 3
GOLD  : [{"o.orderID": "10248", ...}, {"o.orderID": "10248", ...}, {"o.orderID": "10248", ...}]
PRED  : MATCH (o:Order) WHERE o.shipCountry = 'France' RETURN o ORDER BY o.orderDate ASC LIMIT 3
PRED  : [orderID 10248, orderID 10274, orderID ...]   # 3 distinct orders
```

### 6. t122 - GOLD_DEFECT. Gold does not answer its own question.
```
Q     : What is the 'location' of the user who posted the tweet with the earliest 'created_at' date?
GOLD  : MATCH (earliestTweet:Tweet) RETURN earliestTweet ORDER BY earliestTweet.created_at ASC LIMIT 1
GOLD  : [{"earliestTweet": {"_labels": ["Tweet"], "text": "In this week's #twin4j, ...", ...}}]
PRED  : MATCH (u)-[:POSTS]->(t:Tweet) WITH t, u ORDER BY t.created_at ASC LIMIT 1 RETURN u.location
PRED  : [{"u.location": "Graphs Are Everywhere"}]
```

### 7. t071 - GOLD_DEFECT. Gold's sort key is null, so gold's top 3 is 3 nulls.
```
Q     : Which 3 movies have the most number of votes cast by users?
GOLD  : MATCH (m:Movie) RETURN m.title, m.imdbVotes ORDER BY m.imdbVotes DESC LIMIT 3
GOLD  : [{"m.imdbVotes": null, "m.title": "Gate of Heavenly Peace, The"},
         {"m.imdbVotes": null, "m.title": "Wedding Gift, The"}, {"m.imdbVotes": null, ...}]
PRED  : MATCH (u:User)-[:RATED]->(m:Movie) RETURN m.title AS movie, count(u) AS votes
        ORDER BY votes DESC LIMIT 3
PRED  : [{"movie": "Forrest Gump", "votes": 341}, {"movie": "Pulp Fiction", "votes": 324},
         {"movie": "Shawshank Redemption, The", "votes": 311}]
```

### 8. t110 - AMBIGUOUS_QUESTION. "first 3" has no defined order; gold invented one.
```
Q     : What are the first 3 products with a reorder level above 20?
GOLD  : MATCH (p:Product) WHERE p.reorderLevel > 20 RETURN p.productName, p.reorderLevel
        ORDER BY p.productName LIMIT 3
GOLD  : [Aniseed Syrup, Boston Crab Meat, Chang]
PRED  : MATCH (p:Product) WHERE p.reorderLevel > 20 RETURN p LIMIT 3
PRED  : [Chang, Aniseed Syrup, Grandma's Boysenberry Spread]
```

### 9. t002 - AMBIGUOUS_QUESTION. Group by node identity, or by the name the question asks for?
```
Q     : What are the names of the top 3 entities that benefited from filings with amounts less than 100?
GOLD  : MATCH (f:Filing)-[:BENEFITS]->(e:Entity) WHERE f.amount < 100
        WITH e, count(f) AS benefitCount ORDER BY benefitCount DESC RETURN e.name, benefitCount LIMIT 3
GOLD  : [{"e.name": "Vnesheconombank", "benefitCount": 6}, ...]
PRED  : MATCH (f:Filing)-[:BENEFITS]->(e:Entity) WHERE f.amount < 100
        RETURN e.name AS name, count(f) AS numFilings ORDER BY numFilings DESC LIMIT 3
PRED  : [{"name": "Vnesheconombank", "numFilings": 7}, ...]
# two distinct Entity nodes are both named "Vnesheconombank" (6 + 1); gold groups by node, pred by name
```

### 10. t140 - REAL_ERROR. One of only two in 40. Null handling.
```
Q     : Find the top 5 movies released most recently.
GOLD  : MATCH (m:Movie) WHERE m.released IS NOT NULL RETURN m ORDER BY m.released DESC LIMIT 5
GOLD  : [5 real movies]
PRED  : MATCH (m:Movie) RETURN m.title AS title, m.released AS released ORDER BY m.released DESC LIMIT 5
PRED  : [{"title": "Vertigo", "released": null}, {"title": "Wedding Gift, The", "released": null}, ...]
```

## Residual v2 misses on this run, by shape (n = 79 of 200)

| shape | n |
|---|---|
| genuinely different rows | 35 |
| **same rows, projection differs** | **31** |
| different row count | 11 |
| error or empty result | 2 |

The 31 is the ceiling a projection-tolerant scorer would buy, and it is roughly the gap between v2
(60.5%) and the old `score_lenient` (69.5%). We are not claiming it. Two cheaper, honest ways to
close it, both for a human to decide:

1. **Fix the gold projections** in a v2 of the test set (cannot be done here: `data/test.jsonl` is
   frozen by `data/TEST_HASH`). Roughly 30 of 200 gold queries project columns their own question
   does not ask for, or omit ones it does.
2. **Report v2 as the headline and the projection-mismatch count as a stated diagnostic**, which is
   what `RESCORE.md` does.
