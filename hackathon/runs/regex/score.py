#!/usr/bin/env python3
"""Deterministic scorer for natural-language -> Python regex.

A prediction is CORRECT only if, under Python `re.fullmatch`, it matches every positive string
and rejects every negative string stored in the test row. SOFT score = fraction of the 20 strings
handled correctly. A prediction that cannot be extracted or does not compile is INVALID
(correct=False, soft=0). Every match runs in a forked child process with a 1-second timeout, so a
catastrophically backtracking regex cannot hang the eval; a timed-out string counts as wrong.

Usage as a library:  from score import extract_regex, score_row
Self-test:           python3 score.py --test
"""
import multiprocessing
import re
import sys

MATCH_TIMEOUT_S = 1.0
_CTX = multiprocessing.get_context("fork")


def extract_regex(raw):
    """Turn whatever the model said into one regex string, or None."""
    if raw is None:
        return None
    s = str(raw)
    if "</think>" in s:
        s = s.split("</think>")[-1]
    s = s.strip()
    if not s:
        return None
    # 1. fenced code block wins
    m = re.search(r"```[a-zA-Z]*\n?(.*?)```", s, re.S)
    if m:
        s = m.group(1).strip()
    # 2. JSON object with a "regex" key (structured-output runs)
    m = re.search(r'"regex"\s*:\s*"((?:[^"\\]|\\.)*)"', s)
    if m:
        try:
            import json
            return json.loads('"' + m.group(1) + '"')
        except Exception:
            return m.group(1)
    # 3. first non-empty line, minus labels and wrappers
    line = next((l for l in s.splitlines() if l.strip()), "").strip()
    line = re.sub(r"^(regex|pattern|answer|output)\s*[:=]\s*", "", line, flags=re.I)
    line = line.strip()
    # inline code
    m = re.fullmatch(r"`+(.*?)`+", line)
    if m:
        line = m.group(1)
    # python raw-string literal r"..." / r'...'
    m = re.fullmatch(r"[rR]?([\"'])(.*)\1", line)
    if m:
        line = m.group(2)
    # /.../flags
    m = re.fullmatch(r"/(.*)/[a-z]*", line)
    if m and len(line) > 2:
        line = m.group(1)
    line = line.strip()
    return line or None


def _match_child(pattern, s, conn):
    try:
        ok = re.fullmatch(pattern, s) is not None
    except Exception:
        ok = False
    conn.send(ok)
    conn.close()


def fullmatch_timeout(pattern, s, timeout=MATCH_TIMEOUT_S):
    """Return True/False, or None on timeout."""
    parent, child = _CTX.Pipe(duplex=False)
    p = _CTX.Process(target=_match_child, args=(pattern, s, child))
    p.start()
    child.close()
    res = None
    if parent.poll(timeout):
        try:
            res = parent.recv()
        except EOFError:
            res = None
    p.join(0.05)
    if p.is_alive():
        p.kill()
        p.join()
    parent.close()
    return res


def score_row(pred, positives, negatives):
    """pred: regex string or None. Returns a dict."""
    n = len(positives) + len(negatives)
    out = {"pred": pred, "valid": False, "correct": False, "soft": 0.0, "pos_ok": 0, "neg_ok": 0, "timeouts": 0, "error": None}
    if not pred:
        out["error"] = "no regex extracted"
        return out
    try:
        re.compile(pred)
    except re.error as e:
        out["error"] = f"compile error: {e}"
        return out
    except Exception as e:  # OverflowError etc.
        out["error"] = f"compile error: {e}"
        return out
    out["valid"] = True
    for s in positives:
        r = fullmatch_timeout(pred, s)
        if r is None:
            out["timeouts"] += 1
        elif r:
            out["pos_ok"] += 1
    for s in negatives:
        r = fullmatch_timeout(pred, s)
        if r is None:
            out["timeouts"] += 1
        elif r is False:
            out["neg_ok"] += 1
    out["soft"] = round((out["pos_ok"] + out["neg_ok"]) / n, 4)
    out["correct"] = out["pos_ok"] == len(positives) and out["neg_ok"] == len(negatives)
    return out


def _selftest():
    pos = ["cat1", "dog22", "a0"]
    neg = ["cat", "1cat", "", "dog 2"]
    cases = [
        # (raw model output, expected correct, expected valid, note)
        ("[a-z]+[0-9]+", True, True, "plain correct regex"),
        ("```regex\n^[a-z]+\\d+$\n```", True, True, "fenced block with anchors still correct under fullmatch"),
        ('{"regex": "[a-z]+[0-9]+"}', True, True, "json structured output"),
        ("[a-z]+", False, True, "WRONG answer: rejects every positive, must score 0 correct"),
        ("([a-z]+", False, False, "compile error -> invalid"),
        ("", False, False, "empty output -> invalid"),
        ("(a+)+$x" , False, True, "catastrophic pattern must not hang (timeouts count as wrong)"),
    ]
    bad = 0
    for raw, exp_correct, exp_valid, note in cases:
        r = score_row(extract_regex(raw), pos, neg)
        ok = r["correct"] == exp_correct and r["valid"] == exp_valid
        bad += not ok
        print(("PASS" if ok else "FAIL"), f"{note:70s} correct={r['correct']} valid={r['valid']} soft={r['soft']} err={r['error']}")
    # explicit timeout check on a pathological input
    import time
    t0 = time.time()
    r = fullmatch_timeout(r"(a+)+$", "a" * 40 + "b")
    dt = time.time() - t0
    ok = r is None and dt < 3
    bad += not ok
    print(("PASS" if ok else "FAIL"), f"{'timeout fires on catastrophic backtracking':70s} result={r} in {dt:.2f}s")
    # soft score check: regex that handles 5 of 7 strings
    r = score_row("[a-z]+[0-9]*", pos, neg)  # matches pos (3) and 'cat' (wrong), rejects '1cat','' ,'dog 2' -> 6/7
    ok = abs(r["soft"] - round(6 / 7, 4)) < 1e-6 and not r["correct"]
    bad += not ok
    print(("PASS" if ok else "FAIL"), f"{'soft score = 6/7 for a partially right regex':70s} soft={r['soft']}")
    print("ALL PASS" if not bad else f"{bad} FAILURES")
    sys.exit(1 if bad else 0)


if __name__ == "__main__":
    if "--test" in sys.argv:
        _selftest()
    else:
        print(__doc__)
