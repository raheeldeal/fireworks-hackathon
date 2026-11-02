# The Judge

Execution-verified grading as a service. Send your model's Cypher, SQL or regex answers; The Judge runs each one for real and tells you whether its results match our locked gold results.

**Pitch for other teams:** Stop eyeballing whether your text-to-query model "looks right": POST your answers and get a real execution accuracy back in seconds, scored the same way published text-to-Cypher and text-to-SQL papers score. Gold answers never leave the server, so the number you see is an honest held-out score.

## Tasks

| task | rows | answer is | how it is scored |
|---|---|---|---|
| `cypher` | 200 | a Cypher query | Run read-only on Neo4j's public demo graphs (movies, recommendations, northwind, fincen, twitter). Compared with gold rows using `score_v2`: rows as an unordered multiset, column names ignored, node vs its identifying property treated as equal, list vs rows treated as equal, ties at a LIMIT boundary accepted. |
| `sql` | 180 | one SQLite SELECT | Run read-only on Spider dev databases. Rows compared as a multiset; order enforced when the gold query has ORDER BY. |
| `regex` | 200 | a Python regex | `re.fullmatch` must accept all 10 hidden positives and reject all 10 hidden negatives. `soft` = fraction of the 20 handled correctly. |

Verdicts: `correct`, `wrong` (ran, different result), `error` (did not run, or rejected), `empty` (ran, returned nothing while gold has rows). Also `unknown_id` and `duplicate`, which are excluded from the summary.

## API

Base URL: `http://127.0.0.1:8787` locally, or whatever URL your teammate's tunnel prints.

- `GET /health`: liveness and row counts.
- `GET /tasks`: task descriptions and row ids. `GET /tasks?full=true` adds every row's question and schema.
- `GET /tasks/{task}`: rows for one task: `id`, `question`, plus `graph` + `schema` + `tier` (cypher) or `db_id` + `schema` (sql). Never gold.
- `POST /grade`: `{"task": "cypher"|"sql"|"regex", "predictions": [{"id": "t000", "answer": "MATCH ..."}]}`. Returns `summary` (`accuracy` over submitted rows, `accuracy_full_set` counting missing rows as wrong, counts, `error_rate`, `empty_rate`, `soft_accuracy` for regex) and per-row `results` (`verdict`, `n_rows`, `error`, first 5 rows of YOUR result). Answers may be wrapped in code fences or `<think>` blocks; they get cleaned.
- `POST /grade_one`: ad-hoc execution, no gold, no verdict. Cypher: `{"task":"cypher","graph":"movies","answer":"MATCH ..."}`. SQL: `{"task":"sql","db_id":"concert_singer","answer":"SELECT ..."}`. Regex: `{"task":"regex","answer":"\\d+","strings":["123","a1"]}`. Returns up to 50 rows.
- Interactive docs: `GET /docs`.

## Quick start

```bash
./run_local.sh          # creates .venv on first run, serves 127.0.0.1:8787
./examples.sh           # curl examples for every endpoint
```

```bash
curl -s -X POST http://127.0.0.1:8787/grade -H 'Content-Type: application/json' \
  -d '{"task":"cypher","predictions":[{"id":"t000","answer":"MATCH (a:Actor)-[:ACTED_IN]->(:Movie)-[:IN_GENRE]->(g:Genre) RETURN a.name, count(DISTINCT g) AS c ORDER BY c DESC LIMIT 5"}]}'

curl -s -X POST http://127.0.0.1:8787/grade_one -H 'Content-Type: application/json' \
  -d '{"task":"cypher","graph":"movies","answer":"MATCH (m:Movie) RETURN m.title LIMIT 3"}'
```

Python (stdlib only, copy `client.py` into your project):

```python
import os; os.environ["JUDGE_URL"] = "https://<tunnel-url>"
from client import tasks, grade, run
rows = tasks("cypher")
print(grade("cypher", {r["id"]: my_model(r["question"], r["schema"]) for r in rows})["summary"])
```

## Limits

- Read-only. Cypher runs in a READ transaction on a public read-only server, and writes are also rejected up front (`CREATE`, `MERGE`, `DELETE`, `SET`, `REMOVE`, `DROP`, `LOAD CSV`, admin `CALL`s). SQL must be a single SELECT/WITH on a read-only SQLite connection.
- 10 s timeout per execution (regex: 1 s per test string).
- Max 200 predictions per `/grade` call.
- 30 requests per minute per IP (set `JUDGE_RATE_LIMIT` to change). Behind a tunnel the IP comes from `X-Forwarded-For`.
- Never returned: gold queries, gold rows, regex test strings.
- Cypher depends on `demo.neo4jlabs.com` being up. If it is down every Cypher row comes back `error`.

## To expose it

The Judge listens on `127.0.0.1:8787` only. A teammate runs one of these on this laptop with their own account, then shares the printed URL:

```bash
cloudflared tunnel --url http://127.0.0.1:8787     # or
ngrok http 8787
```

Then other teams set `JUDGE_URL=<printed https URL>` for `client.py` / `examples.sh`. Close the tunnel to take it offline.

## Files

- `app.py`: the FastAPI service. Imports `cypher/executor.py` and `cypher/score.py`, `runs/text-to-sql/score.py`, `runs/regex/score.py` by path without modifying them; reads `cypher/audit/exec_cache.json` read-only for the LIMIT-tie rule.
- `run_local.sh`, `examples.sh`, `client.py`.

## Verified

Grading our own `glm-5p3-flash` predictions (`cypher/results_v2/glm-5p3-flash_v1_plain_n200.json`) through `/grade` gives 121/200 = 60.5%, with all 200 per-row verdicts identical to the offline scorer, in about 10 s. Gold answers graded through `/grade` score 100% for SQL (180/180) and regex (200/200).
