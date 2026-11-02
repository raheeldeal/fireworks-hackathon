#!/usr/bin/env bash
# Start The Judge on 127.0.0.1:8787. First run creates judge/.venv.
set -euo pipefail
cd "$(dirname "$0")"
if [ ! -x .venv/bin/python ]; then
  python3.11 -m venv .venv 2>/dev/null || python3 -m venv .venv
  .venv/bin/pip install -q fastapi uvicorn neo4j
fi
exec .venv/bin/python -m uvicorn app:app --host 127.0.0.1 --port "${PORT:-8787}" --workers 1
