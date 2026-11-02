"""CypherBench's two smallest full test graphs; same result contract as executor.py."""
import os
import threading
import time

from neo4j import GraphDatabase, READ_ACCESS, unit_of_work
from executor import to_py

PORTS = {"flight_accident": 15064, "nba": 15067}
MAX_ROWS = 10000
_drivers, _lock = {}, threading.Lock()


def _driver(graph):
    if graph not in PORTS:
        raise ValueError(f"Unsupported CypherBench graph: {graph}")
    with _lock:
        if graph not in _drivers:
            uri = os.getenv(f"CYPHERBENCH_{graph.upper()}_URI", f"bolt://127.0.0.1:{PORTS[graph]}")
            _drivers[graph] = GraphDatabase.driver(
                uri, auth=(os.getenv("CYPHERBENCH_USER", "neo4j"),
                           os.getenv("CYPHERBENCH_PASSWORD", "cypherbench")),
                connection_timeout=5, connection_acquisition_timeout=10,
                max_transaction_retry_time=0, max_connection_pool_size=8)
        return _drivers[graph]


def execute(graph, cypher, timeout=30):
    start = time.monotonic()
    try:
        if not cypher or not cypher.strip():
            raise ValueError("no query")

        @unit_of_work(timeout=timeout)
        def work(tx):
            # Community edition READ_ACCESS alone is not a write authorization barrier.
            if tx.run("EXPLAIN " + cypher).consume().query_type != "r":
                raise ValueError("Only read queries are allowed")
            result = tx.run(cypher)
            columns = list(result.keys())
            rows = []
            for record in result:
                rows.append({c: to_py(record[c]) for c in columns})
                if len(rows) > MAX_ROWS:
                    raise ValueError(f"Result exceeds {MAX_ROWS} rows; refusing truncated scoring")
            result.consume()
            return columns, rows

        with _driver(graph).session(database="neo4j", default_access_mode=READ_ACCESS) as session:
            columns, rows = session.execute_read(work)
        return {"ok": True, "rows": rows, "columns": columns, "error": None,
                "secs": round(time.monotonic() - start, 3)}
    except Exception as exc:
        return {"ok": False, "rows": [], "columns": [],
                "error": f"{type(exc).__name__}: {str(exc)[:300]}",
                "secs": round(time.monotonic() - start, 3)}
