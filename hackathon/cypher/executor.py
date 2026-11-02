"""Run a Cypher query read-only against Neo4j's public demo graphs.

Backend: neo4j+s://demo.neo4jlabs.com, user = password = database name (Neo4j Labs public read-only demo server).
execute(graph, cypher) -> {"ok": bool, "rows": [dict], "columns": [str], "error": str|None, "secs": float,
                           "warnings": [str]}
`warnings` holds the server's warning notifications (GQL status 01xxx), e.g. "property key does not exist".
A query with such a warning still runs and may return rows, but it usually means a misspelt name.
"""
import time, datetime, threading, logging
from neo4j import GraphDatabase, READ_ACCESS, unit_of_work

logging.getLogger("neo4j.notifications").setLevel(logging.ERROR)  # we read warnings from the summary instead
from neo4j.graph import Node, Relationship, Path
import neo4j.time, neo4j.spatial

URI = "neo4j+s://demo.neo4jlabs.com"
TIMEOUT_S = 10
MAX_ROWS = 1000
GRAPHS = ["movies", "recommendations", "northwind", "fincen", "twitter"]
_drivers, _lock = {}, threading.Lock()


def _driver(graph):
    with _lock:
        if graph not in _drivers:
            _drivers[graph] = GraphDatabase.driver(URI, auth=(graph, graph), connection_timeout=10,
                                                   max_connection_pool_size=16)
        return _drivers[graph]


def to_py(v):
    """Make driver values JSON-friendly and comparable."""
    if isinstance(v, Node):
        return {"_labels": sorted(v.labels), **{k: to_py(x) for k, x in v.items()}}
    if isinstance(v, Relationship):
        return {"_type": v.type, **{k: to_py(x) for k, x in v.items()}}
    if isinstance(v, Path):
        return [to_py(n) for n in v.nodes]
    if isinstance(v, (list, tuple)):
        return [to_py(x) for x in v]
    if isinstance(v, dict):
        return {k: to_py(x) for k, x in v.items()}
    if isinstance(v, (neo4j.time.DateTime, neo4j.time.Date, neo4j.time.Time, neo4j.time.Duration,
                      datetime.date, datetime.datetime)):
        return str(v)
    if isinstance(v, neo4j.spatial.Point):
        return list(v)
    return v


def execute(graph, cypher, timeout=TIMEOUT_S):
    t0 = time.time()
    if not cypher or not cypher.strip():
        return {"ok": False, "rows": [], "columns": [], "error": "no query", "secs": 0.0, "warnings": []}

    @unit_of_work(timeout=timeout)
    def work(tx):
        res = tx.run(cypher)
        cols = list(res.keys())
        rows = []
        for rec in res:
            rows.append({k: to_py(rec[k]) for k in cols})
            if len(rows) >= MAX_ROWS:
                break
        summary = res.consume()
        warnings = [g.status_description for g in summary.gql_status_objects
                    if g.is_notification and g.gql_status.startswith("01")]
        return cols, rows, warnings

    try:
        with _driver(graph).session(database=graph, default_access_mode=READ_ACCESS) as s:
            cols, rows, warnings = s.execute_read(work)  # read transaction: server rejects writes
        return {"ok": True, "rows": rows, "columns": cols, "error": None, "secs": round(time.time() - t0, 3),
                "warnings": warnings}
    except Exception as e:
        return {"ok": False, "rows": [], "columns": [], "error": f"{type(e).__name__}: {str(e)[:300]}",
                "secs": round(time.time() - t0, 3), "warnings": []}


if __name__ == "__main__":
    for g in GRAPHS:
        r = execute(g, "MATCH (n) RETURN labels(n)[0] AS label, count(*) AS c ORDER BY c DESC LIMIT 3")
        print(g, r["ok"], r["secs"], r["rows"] or r["error"])
    print(execute("movies", "CREATE (n:Hack) RETURN n")["error"])
