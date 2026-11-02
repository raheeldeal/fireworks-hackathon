#!/usr/bin/env python3
"""Deterministic scorer for code-fix: run the model's function against hidden unit tests in a sandbox.

score(raw_model_output, row) -> dict(status=..., correct=0/1, invalid=0/1, detail=str)
  pass          -> correct=1
  fail/timeout  -> correct=0
  invalid       -> correct=0, invalid=1  (no code block / no def of the entry point / syntax error)
Normalization: strips <think> blocks, takes the last ```python block (or the whole text if none),
and drops any stray test code the model appended (lines after the function that call check/assert).
Run `python3 score.py` to execute the 5 built-in unit tests.
"""
import ast
import json
import re
import sys

from sandbox import run_program, syntax_ok

FENCE = re.compile(r"```(?:python|py)?\s*\n(.*?)```", re.DOTALL | re.IGNORECASE)


def extract_code(raw: str) -> str:
    if not raw:
        return ""
    if "</think>" in raw:
        raw = raw.split("</think>")[-1]
    blocks = FENCE.findall(raw)
    if blocks:
        # prefer the last block that defines a function
        for b in reversed(blocks):
            if "def " in b:
                return b.strip("\n") + "\n"
        return blocks[-1].strip("\n") + "\n"
    # JSON-mode output: {"fixed_code": "..."}
    s = raw.strip()
    if s.startswith("{"):
        try:
            obj = json.loads(s)
            for k in ("fixed_code", "code", "function"):
                if isinstance(obj.get(k), str):
                    inner = FENCE.findall(obj[k])  # models often put a fenced block inside the JSON string
                    return (inner[-1] if inner else obj[k]).strip("\n") + "\n"
        except json.JSONDecodeError:
            pass
    return raw.strip("\n") + "\n"


def strip_trailing_tests(code: str) -> str:
    """Remove top-level statements after the last def/import/class (e.g. model-added asserts or prints)."""
    try:
        tree = ast.parse(code)
    except SyntaxError:
        return code
    keep = [n for n in tree.body if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef,
                                                   ast.Import, ast.ImportFrom, ast.Assign))]
    if len(keep) == len(tree.body):
        return code
    return ast.unparse(ast.Module(body=keep, type_ignores=[])) + "\n"


def score(raw: str, row: dict) -> dict:
    code = extract_code(raw)
    if not code.strip():
        return {"status": "invalid", "correct": 0, "invalid": 1, "detail": "empty output"}
    ok, msg = syntax_ok(code)
    if not ok:
        return {"status": "invalid", "correct": 0, "invalid": 1, "detail": msg}
    code = strip_trailing_tests(code)
    if not re.search(rf"^\s*def\s+{re.escape(row['entry_point'])}\s*\(", code, re.M):
        return {"status": "invalid", "correct": 0, "invalid": 1, "detail": f"no def {row['entry_point']}"}
    program = row["test_program_prefix"] + code + row["test_program_suffix"]
    status, detail = run_program(program)
    return {"status": status, "correct": int(status == "pass"), "invalid": 0, "detail": detail}


# ---------------- unit tests ----------------
_ROW = {
    "entry_point": "add_one",
    "test_program_prefix": "",
    "test_program_suffix": "\nassert add_one(1) == 2\nassert add_one(-1) == 0\n",
}


def _tests():
    cases = [
        ("correct fenced", "Here you go:\n```python\ndef add_one(x):\n    return x + 1\n```", "pass", 1, 0),
        ("wrong answer", "```python\ndef add_one(x):\n    return x + 2\n```", "fail", 0, 0),
        ("syntax error -> invalid", "```python\ndef add_one(x)\n    return x + 1\n```", "invalid", 0, 1),
        ("think block + bare code + stray test", "<think>hmm</think>\ndef add_one(x):\n    return x + 1\n\nprint(add_one(3))\nassert add_one(0) == 5\n", "pass", 1, 0),
        ("wrong function name -> invalid", "```python\ndef add_two(x):\n    return x + 1\n```", "invalid", 0, 1),
        ("infinite loop -> fail", "```python\ndef add_one(x):\n    while True:\n        pass\n```", "timeout", 0, 0),
    ]
    bad = 0
    for name, raw, st, c, inv in cases:
        r = score(raw, _ROW)
        ok = r["status"] == st and r["correct"] == c and r["invalid"] == inv
        print(("ok  " if ok else "FAIL"), name, "->", r["status"], r["detail"][:60])
        bad += not ok
    sys.exit(1 if bad else 0)


if __name__ == "__main__":
    _tests()
