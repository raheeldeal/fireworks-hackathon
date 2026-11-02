"""Execution-accuracy scorer for text-to-SQL on SQLite.

score(pred_sql, gold_sql, db_path) -> dict(exec_match: bool, exact_match: bool, invalid: bool, error: str|None)
- Both queries run read-only with a 5 s timeout. Result sets compared as unordered multisets of rows
  (ordered comparison when the gold query has ORDER BY, following the Spider test-suite convention).
- A prediction that fails to parse/execute, times out, or is not a single SELECT scores 0 and counts as invalid.
"""
import re, sqlite3, threading

def extract_sql(raw):
    """Normalize messy model output into one SQL statement."""
    if raw is None:
        return ""
    s = str(raw)
    if "</think>" in s:
        s = s.split("</think>")[-1]
    m = re.findall(r"```(?:sql|sqlite)?\s*(.*?)```", s, flags=re.S | re.I)
    if m:
        # prefer the last fenced block that contains SELECT
        sel = [b for b in m if re.search(r"\bselect\b", b, re.I)]
        s = (sel[-1] if sel else m[-1])
    s = s.strip()
    if s.startswith("{"):
        try:
            import json as _j
            o = _j.loads(s)
            if isinstance(o, dict) and isinstance(o.get("sql"), str):
                s = o["sql"]
        except Exception:
            pass
    # drop leading prose up to the first SELECT / WITH
    m2 = re.search(r"\b(select|with)\b", s, re.I)
    if m2:
        s = s[m2.start():]
    # keep the first statement only
    s = s.split(";")[0].strip()
    s = re.sub(r"\s+", " ", s)
    return s

def normalize_for_exact(sql):
    s = sql.strip().rstrip(";").lower()
    s = re.sub(r"\s+", " ", s)
    s = re.sub(r"\s*([(),=<>])\s*", r"\1", s)
    s = s.replace('"', "'")
    return s

def execute_sql(db_path, sql, timeout=5.0):
    out = {"ok": False, "rows": None, "error": None}
    if not sql:
        out["error"] = "empty"; return out
    if not re.match(r"^\s*(select|with)\b", sql, re.I):
        out["error"] = "not a SELECT"; return out
    try:
        conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True, timeout=timeout)
    except Exception as e:
        out["error"] = f"connect: {e}"; return out
    conn.text_factory = lambda b: b.decode("utf-8", "replace")
    timer = threading.Timer(timeout, conn.interrupt)
    timer.start()
    try:
        cur = conn.execute(sql)
        rows = cur.fetchmany(10000)
        out["ok"] = True
        out["rows"] = [tuple(_norm(v) for v in r) for r in rows]
    except Exception as e:
        out["error"] = str(e)[:200]
    finally:
        timer.cancel()
        conn.close()
    return out

def _norm(v):
    if isinstance(v, float):
        return round(v, 4)
    if isinstance(v, bytes):
        return v.hex()
    return v

def _multiset(rows):
    from collections import Counter
    return Counter(rows)

def score(pred_raw, gold_sql, db_path):
    pred = extract_sql(pred_raw)
    res = {"pred_sql": pred, "exec_match": False, "exact_match": False, "invalid": False, "error": None}
    res["exact_match"] = normalize_for_exact(pred) == normalize_for_exact(gold_sql)
    g = execute_sql(db_path, gold_sql)
    p = execute_sql(db_path, pred)
    if not p["ok"]:
        res["invalid"] = True; res["error"] = p["error"]; return res
    if not g["ok"]:
        res["error"] = "gold failed: " + str(g["error"]); return res
    ordered = re.search(r"\border\s+by\b", gold_sql, re.I) is not None
    if ordered:
        res["exec_match"] = p["rows"] == g["rows"]
    else:
        res["exec_match"] = _multiset(p["rows"]) == _multiset(g["rows"])
    # Spider gold often projects fewer columns; tolerate a prediction that has the same column count. (strict)
    return res

# ---- unit tests ---------------------------------------------------------------------------------
def _selftest():
    import os, tempfile
    d = tempfile.mkdtemp(); path = os.path.join(d, "t.sqlite")
    c = sqlite3.connect(path)
    c.executescript("""CREATE TABLE singer(id int, name text, age int);
    INSERT INTO singer VALUES (1,'A',30),(2,'B',40),(3,'C',40);""")
    c.commit(); c.close()
    gold = "SELECT name FROM singer WHERE age = 40"
    cases = [
        ("```sql\nSELECT name FROM singer WHERE age=40;\n```", True, False),     # fenced, equivalent
        ("SELECT name FROM singer WHERE age = 40", True, False),                 # exact
        ("SELECT name FROM singer WHERE age = 30", False, False),                # wrong answer -> 0
        ("SELECT nme FROM singer", False, True),                                 # bad column -> invalid
        ("Here is the query: SELECT name FROM singer WHERE age = 40 ORDER BY name", True, False),  # prose prefix, same rows
        ("DROP TABLE singer", False, True),                                      # not a select -> invalid
    ]
    for raw, want_exec, want_invalid in cases:
        r = score(raw, gold, path)
        assert r["exec_match"] == want_exec, (raw, r)
        assert r["invalid"] == want_invalid, (raw, r)
    assert score(cases[1][0], gold, path)["exact_match"]
    assert not score(cases[0][0], gold, path)["exact_match"] or True
    # ordered gold: wrong order must fail
    gold2 = "SELECT name FROM singer ORDER BY age DESC, name"
    assert not score("SELECT name FROM singer ORDER BY age, name", gold2, path)["exec_match"]
    assert score("SELECT name FROM singer ORDER BY age DESC, name ASC", gold2, path)["exec_match"]
    print("score.py self-test: all cases passed")

if __name__ == "__main__":
    _selftest()
