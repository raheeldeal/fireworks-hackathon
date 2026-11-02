#!/usr/bin/env bash
# curl examples for The Judge. JUDGE_URL defaults to the local server.
J="${JUDGE_URL:-http://127.0.0.1:8787}"
set -x
curl -s "$J/health"; echo
curl -s "$J/tasks" | head -c 400; echo                       # ids per task
curl -s "$J/tasks/cypher" | head -c 600; echo                # questions + schemas, no gold
# grade a batch (up to 200 per call)
curl -s -X POST "$J/grade" -H 'Content-Type: application/json' -d '{
  "task": "cypher",
  "predictions": [
    {"id": "t000", "answer": "MATCH (a:Actor)-[:ACTED_IN]->(:Movie)-[:IN_GENRE]->(g:Genre) RETURN a.name, count(DISTINCT g) AS c ORDER BY c DESC LIMIT 5"},
    {"id": "t001", "answer": "MATCH (n) RETURN n LIMIT 1"}
  ]}'; echo
curl -s -X POST "$J/grade" -H 'Content-Type: application/json' -d '{"task":"sql","predictions":[{"id":"dev0001","answer":"SELECT count(*) FROM singer"}]}'; echo
curl -s -X POST "$J/grade" -H 'Content-Type: application/json' -d '{"task":"regex","predictions":[{"id":"kb13-766","answer":".*\\bmonkey\\b.*wrench"}]}'; echo
# ad-hoc: run any read-only query, see the rows (no verdict)
curl -s -X POST "$J/grade_one" -H 'Content-Type: application/json' -d '{"task":"cypher","graph":"movies","answer":"MATCH (m:Movie) RETURN m.title LIMIT 3"}'; echo
curl -s -X POST "$J/grade_one" -H 'Content-Type: application/json' -d '{"task":"sql","db_id":"concert_singer","answer":"SELECT name FROM singer LIMIT 3"}'; echo
curl -s -X POST "$J/grade_one" -H 'Content-Type: application/json' -d '{"task":"regex","answer":"\\d{3}-\\d{4}","strings":["555-1234","5551234"]}'; echo
# writes are rejected
curl -s -X POST "$J/grade_one" -H 'Content-Type: application/json' -d '{"task":"cypher","graph":"movies","answer":"CREATE (n:Hack) RETURN n"}'; echo
