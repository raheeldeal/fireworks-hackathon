#!/usr/bin/env python3
"""Run untrusted Python (model output + tests) in a subprocess with a timeout and no network.

Never execs model output in this process. Uses macOS sandbox-exec to deny network when available,
plus `python3 -I` (isolated mode: no user site, no env-based path injection) and an empty environment.
Returns (status, message): status in {"pass", "fail", "timeout", "syntax_error", "invalid"}.
"""
import ast
import os
import shutil
import subprocess
import sys
import tempfile

TIMEOUT_S = 10
PYTHON = sys.executable
SANDBOX_PROFILE = '(version 1)(allow default)(deny network*)'

PREAMBLE = """
import socket as _s
def _blocked(*a, **k): raise OSError("network disabled in sandbox")
_s.socket = _blocked; _s.create_connection = _blocked
import sys as _sys; _sys.setrecursionlimit(5000)
"""


def syntax_ok(code: str):
    try:
        ast.parse(code)
        return True, ""
    except SyntaxError as e:
        return False, f"SyntaxError: {e.msg} (line {e.lineno})"


def run_program(source: str, timeout: float = TIMEOUT_S):
    """Write `source` to a temp file and run it. Returns (status, stderr_tail)."""
    ok, msg = syntax_ok(source)
    if not ok:
        return "syntax_error", msg
    with tempfile.TemporaryDirectory() as td:
        path = os.path.join(td, "prog.py")
        have_sandbox = bool(shutil.which("sandbox-exec"))
        with open(path, "w") as f:
            # sandbox-exec blocks network at the OS level; the socket stub is only a fallback elsewhere
            f.write(("" if have_sandbox else PREAMBLE) + "\n" + source)
        cmd = [PYTHON, "-I", path]
        if have_sandbox:
            cmd = ["sandbox-exec", "-p", SANDBOX_PROFILE] + cmd
        try:
            p = subprocess.run(cmd, cwd=td, capture_output=True, text=True, timeout=timeout,
                               env={"PATH": "/usr/bin:/bin", "HOME": td})
        except subprocess.TimeoutExpired:
            return "timeout", f"Timeout: test did not finish within {int(timeout)} seconds"
    if p.returncode == 0:
        return "pass", ""
    return "fail", tail(p.stderr)


def tail(stderr: str, max_lines: int = 6, max_chars: int = 600) -> str:
    """Keep the useful end of a traceback: the failing source line and the exception line."""
    lines = [l for l in stderr.strip().splitlines() if l.strip()]
    # drop the "File ..." frames pointing at our temp file path, keep the code lines and exception
    keep = []
    for l in lines:
        if l.strip().startswith("File "):
            continue  # drop frame headers (temp paths, line numbers); keep source lines and the exception
        keep.append(l.rstrip())
    out = "\n".join(keep[-max_lines:])
    return out[-max_chars:]


if __name__ == "__main__":
    print(run_program("def f(x):\n    return x+1\nassert f(1) == 3\n"))
    print(run_program("def f(x):\n    return x+1\nassert f(1) == 2\n"))
    print(run_program("while True: pass\n", timeout=2))
    print(run_program("def f(:\n  pass\n"))
    print(run_program("import urllib.request\nurllib.request.urlopen('https://example.com', timeout=3)\n"))
