"""Run this repo's run_eval.py (same harness, same scorer) on the CypherBench held-out graphs.
Only change: executor.execute is pointed at the local CypherBench Neo4j containers before the harness imports it.
  python cypherbench/run_cb.py --tag cb_r6bx_ftbx --model-path <lora> --shots 3 --fix --repair 3 --escalate kimi-k3 \
      --data cypherbench/test.jsonl --no-trace
"""
import os, sys
CY = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, CY)
import executor as _ex
sys.path.insert(1, os.path.join(CY, "cypherbench"))
import cypherbench_executor as _cbx
def _execute(graph, cypher, *a, **k):
    r = _cbx.execute(graph, cypher)
    r.setdefault("warnings", [])
    return r
_ex.execute = _execute
os.chdir(CY)
import run_eval
run_eval.main()
