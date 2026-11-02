"""The Judge: execution-verified grading for text-to-Cypher, text-to-SQL and NL-to-regex.

Predictions are executed for real (Neo4j demo graphs, Spider SQLite DBs, Python re) and compared
with our locked gold results. Gold queries, gold rows and regex test strings are never returned.
Run: ./run_local.sh  (serves on 127.0.0.1:8787)
"""
import hashlib, importlib.util, json, logging, os, re, subprocess, sys, threading, time
from collections import defaultdict, deque
from concurrent.futures import ThreadPoolExecutor

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)  # .../hackathon
CYPHER_DIR = os.path.join(ROOT, "cypher")
SQL_DIR = os.path.join(ROOT, "runs", "text-to-sql")
REGEX_DIR = os.path.join(ROOT, "runs", "regex")
SPIDER_DB = os.path.join(SQL_DIR, "raw", "zip", "spider_data", "database")

TIMEOUT_S = 10
MAX_PREDS = 200
RATE_LIMIT = int(os.environ.get("JUDGE_RATE_LIMIT", "30"))  # requests per IP per 60 s
WORKERS = 8
ROW_PREVIEW = 5      # rows of the PREDICTION shown back in /grade (never gold rows)
ONE_ROWS = 50        # rows shown back in /grade_one

logging.getLogger("neo4j").setLevel(logging.ERROR)


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


# executor.py imports nothing from the project, score.py only stdlib; load both by path (read-only).
cy_exec = _load("cy_executor", os.path.join(CYPHER_DIR, "executor.py"))
cy_score = _load("cy_score", os.path.join(CYPHER_DIR, "score.py"))
sql_score = _load("sql_score", os.path.join(SQL_DIR, "score.py"))


def _jsonl(path):
    with open(path) as f:
        return [json.loads(l) for l in f if l.strip()]


CYPHER = {r["id"]: r for r in _jsonl(os.path.join(CYPHER_DIR, "data", "test.jsonl"))}
SQL = {r["id"]: r for r in _jsonl(os.path.join(SQL_DIR, "data", "test.jsonl"))}
REGEX = {r["id"]: r for r in _jsonl(os.path.join(REGEX_DIR, "data", "test.jsonl"))}

# Executed result of each LIMIT gold query with LIMIT stripped (needed by score_v2 rule R9).
# Seeded read-only from our audit cache; anything missing is executed live once and memoized.
_EXEC_CACHE_PATH = os.path.join(CYPHER_DIR, "audit", "exec_cache.json")
_EXEC_CACHE = json.load(open(_EXEC_CACHE_PATH)) if os.path.exists(_EXEC_CACHE_PATH) else {}
_unl_lock = threading.Lock()
_POOL = ThreadPoolExecutor(max_workers=WORKERS)


def _ckey(graph, cypher):
    return hashlib.sha1((graph + "\x00" + (cypher or "")).encode()).hexdigest()


def gold_unlimited(ex):
    if not ex["complexity"]["limit"]:
        return None
    q = cy_score.strip_limit(ex["cypher"])
    k = _ckey(ex["graph"], q)
    with _unl_lock:
        if k in _EXEC_CACHE:
            return _EXEC_CACHE[k]
    r = cy_exec.execute(ex["graph"], q, timeout=TIMEOUT_S)
    if r.get("ok"):
        with _unl_lock:
            _EXEC_CACHE[k] = r
    return r


# ---------------------------------------------------------------- write guards
def _strip_literals(q):
    q = re.sub(r"'(?:[^'\\]|\\.)*'|\"(?:[^\"\\]|\\.)*\"|`[^`]*`", "''", q)
    q = re.sub(r"//[^\n]*|/\*.*?\*/", " ", q, flags=re.S)
    return q


CYPHER_WRITE = re.compile(
    r"\b(create|merge|delete|detach|set|remove|drop|foreach|load\s+csv|in\s+transactions|grant|revoke|deny|alter|rename)\b"
    r"|\bcall\s+(dbms|db\.(create|drop|index|clear)|apoc\.(create|merge|refactor|periodic|load|export|trigger|schema|nodes\.delete|do|cypher\.run(write|schema)))",
    re.I)
SQL_WRITE = re.compile(r"\b(insert|update|delete|drop|create|alter|attach|detach|pragma|replace|vacuum|reindex)\b", re.I)


def cypher_write_reason(q):
    m = CYPHER_WRITE.search(_strip_literals(q or ""))
    return f"rejected: write/admin keyword '{m.group(0)}' not allowed (read-only judge)" if m else None


def sql_write_reason(q):
    s = _strip_literals(q or "")
    if not re.match(r"^\s*(select|with)\b", s, re.I):
        return "rejected: only a single SELECT/WITH statement is allowed"
    m = SQL_WRITE.search(s)
    return f"rejected: write/admin keyword '{m.group(0)}' not allowed (read-only judge)" if m else None


# ---------------------------------------------------------------- rate limit
_hits = defaultdict(deque)
_hits_lock = threading.Lock()


def rate_limit(request: Request):
    ip = request.client.host if request.client else "?"
    fwd = request.headers.get("x-forwarded-for")  # behind a tunnel every client looks like 127.0.0.1
    if fwd:
        ip = fwd.split(",")[0].strip()
    now = time.time()
    with _hits_lock:
        q = _hits[ip]
        while q and now - q[0] > 60:
            q.popleft()
        if len(q) >= RATE_LIMIT:
            raise HTTPException(429, f"rate limit: {RATE_LIMIT} requests per minute per IP; retry in {int(61 - (now - q[0]))} s")
        q.append(now)


# ---------------------------------------------------------------- graders
def grade_cypher_row(ex, answer):
    q = cy_score.clean_pred(answer or "")
    if not q:
        return {"verdict": "error", "n_rows": 0, "error": "no query"}
    why = cypher_write_reason(q)
    if why:
        return {"verdict": "error", "n_rows": 0, "error": why}
    pred = cy_exec.execute(ex["graph"], q, timeout=TIMEOUT_S)
    gold = {"ok": True, **ex["gold_result"]}
    v = cy_score.score_v2(gold, pred, ex["cypher"], gold_unlimited(ex))
    return {"verdict": v, "n_rows": len(pred["rows"]), "error": pred.get("error"),
            "rows_head": pred["rows"][:ROW_PREVIEW], "secs": pred.get("secs")}


def _sql_db(db_id):
    if not re.fullmatch(r"[A-Za-z0-9_]+", db_id or ""):
        return None
    p = os.path.join(SPIDER_DB, db_id, db_id + ".sqlite")
    return p if os.path.exists(p) else None


def grade_sql_row(ex, answer):
    q = sql_score.extract_sql(answer or "")
    if not q:
        return {"verdict": "error", "n_rows": 0, "error": "no query"}
    why = sql_write_reason(q)
    if why:
        return {"verdict": "error", "n_rows": 0, "error": why}
    db = _sql_db(ex["db_id"])
    p = sql_score.execute_sql(db, q, timeout=TIMEOUT_S)
    if not p["ok"]:
        return {"verdict": "error", "n_rows": 0, "error": p["error"]}
    g = sql_score.execute_sql(db, ex["gold_sql"], timeout=TIMEOUT_S)
    if not g["ok"]:
        return {"verdict": "error", "n_rows": len(p["rows"]), "error": "gold failed to execute (judge-side issue)"}
    if not p["rows"]:
        v = "correct" if not g["rows"] else "empty"
    elif re.search(r"\border\s+by\b", ex["gold_sql"], re.I):
        v = "correct" if p["rows"] == g["rows"] else "wrong"
    else:
        v = "correct" if sql_score._multiset(p["rows"]) == sql_score._multiset(g["rows"]) else "wrong"
    return {"verdict": v, "n_rows": len(p["rows"]), "error": None, "rows_head": [list(r) for r in p["rows"][:ROW_PREVIEW]]}


_REGEX_CHILD = r"""
import json, sys, importlib.util
spec = importlib.util.spec_from_file_location("rx", sys.argv[1]); rx = importlib.util.module_from_spec(spec); spec.loader.exec_module(rx)
out = []
for j in json.load(sys.stdin):
    pat = rx.extract_regex(j["answer"]) if j.get("answer") else None
    if j.get("strings") is not None:
        try:
            rx.re.compile(pat or "")
            out.append({"pattern": pat, "matches": [rx.fullmatch_timeout(pat, s) for s in j["strings"]]} if pat else {"pattern": None})
        except Exception as e:
            out.append({"pattern": pat, "error": "compile error: %s" % e})
    else:
        out.append(rx.score_row(pat, j["pos"], j["neg"]))
print(json.dumps(out))
"""


def _regex_child(jobs, timeout):
    # Python's re cannot be interrupted in-thread, so scoring runs in a fresh single-threaded process
    # (the regex scorer forks one child per string with a 1 s timeout).
    r = subprocess.run([sys.executable, "-c", _REGEX_CHILD, os.path.join(REGEX_DIR, "score.py")],
                       input=json.dumps(jobs), capture_output=True, text=True, timeout=timeout)
    if r.returncode != 0:
        raise HTTPException(500, "regex scorer failed: " + r.stderr[-300:])
    return json.loads(r.stdout)


def grade_regex_rows(items):
    jobs = [{"answer": a, "pos": ex["positives"], "neg": ex["negatives"]} for ex, a in items]
    res = _regex_child(jobs, timeout=30 + 2 * len(jobs))
    out = []
    for r in res:
        if not r["valid"]:
            v = "error"
        elif r["correct"]:
            v = "correct"
        else:
            v = "wrong"
        # only counts are returned; the hidden test strings stay hidden
        out.append({"verdict": v, "n_rows": None, "error": r["error"], "soft": r["soft"],
                    "pos_ok": r["pos_ok"], "neg_ok": r["neg_ok"], "timeouts": r["timeouts"]})
    return out


TASKS = {
    "cypher": {"rows": CYPHER, "desc": "Text-to-Cypher on Neo4j public demo graphs (movies, recommendations, northwind, fincen, twitter). Answer = a Cypher query. Scored by execution with score_v2 (unordered row multiset, node<->identifying property, list<->rows, LIMIT tie rules)."},
    "sql": {"rows": SQL, "desc": "Text-to-SQL on Spider dev SQLite DBs. Answer = one SQLite SELECT. Scored by execution: unordered multiset of rows, ordered when gold has ORDER BY."},
    "regex": {"rows": REGEX, "desc": "Natural language to Python regex. Answer = a regex. Correct only if re.fullmatch accepts all 10 hidden positives and rejects all 10 hidden negatives; soft = fraction right."},
}


def public_row(task, r):
    if task == "cypher":
        return {"id": r["id"], "question": r["question"], "graph": r["graph"], "schema": r["schema"], "tier": r["complexity"]["tier"]}
    if task == "sql":
        return {"id": r["id"], "question": r["question"], "db_id": r["db_id"], "schema": r["schema"]}
    return {"id": r["id"], "question": r["text"]}


# ---------------------------------------------------------------- API
app = FastAPI(title="The Judge", version="1.0",
              description="Execution-verified grading for text-to-Cypher, text-to-SQL and NL-to-regex. Gold is never returned.")


class Pred(BaseModel):
    id: str
    answer: str = ""


class GradeReq(BaseModel):
    task: str
    predictions: list[Pred] = Field(default_factory=list)


class GradeOneReq(BaseModel):
    task: str = "cypher"
    answer: str
    question: str = ""
    graph: str | None = None       # cypher
    db_id: str | None = None       # sql
    strings: list[str] | None = None  # regex: strings to test with fullmatch


@app.get("/")
def root():
    return {"name": "The Judge", "endpoints": ["GET /health", "GET /tasks", "GET /tasks/{task}", "POST /grade", "POST /grade_one"],
            "limits": {"timeout_s_per_execution": TIMEOUT_S, "max_predictions_per_call": MAX_PREDS,
                       "rate_limit_per_ip_per_min": RATE_LIMIT, "read_only": True}}


@app.get("/health")
def health():
    return {"ok": True, "tasks": {k: len(v["rows"]) for k, v in TASKS.items()}}


@app.get("/tasks")
def tasks(request: Request, full: bool = False):
    """Task list. ?full=true includes every row's question and schema (large); otherwise ids only."""
    rate_limit(request)
    out = {}
    for t, spec in TASKS.items():
        rows = list(spec["rows"].values())
        out[t] = {"description": spec["desc"], "n": len(rows),
                  "rows": [public_row(t, r) for r in rows] if full else [r["id"] for r in rows]}
    return out


@app.get("/tasks/{task}")
def task_rows(task: str, request: Request):
    rate_limit(request)
    if task not in TASKS:
        raise HTTPException(404, f"unknown task '{task}'; choose from {list(TASKS)}")
    return {"task": task, "description": TASKS[task]["desc"],
            "rows": [public_row(task, r) for r in TASKS[task]["rows"].values()]}


@app.post("/grade")
def grade(req: GradeReq, request: Request):
    rate_limit(request)
    if req.task not in TASKS:
        raise HTTPException(400, f"unknown task '{req.task}'; choose from {list(TASKS)}")
    if not req.predictions:
        raise HTTPException(400, "predictions is empty")
    if len(req.predictions) > MAX_PREDS:
        raise HTTPException(413, f"max {MAX_PREDS} predictions per call; split into batches")
    t0 = time.time()
    rows = TASKS[req.task]["rows"]
    seen, results, todo = set(), [None] * len(req.predictions), []
    for i, p in enumerate(req.predictions):
        if p.id not in rows:
            results[i] = {"id": p.id, "verdict": "unknown_id", "n_rows": None, "error": "id not in task"}
        elif p.id in seen:
            results[i] = {"id": p.id, "verdict": "duplicate", "n_rows": None, "error": "id already graded in this call"}
        else:
            seen.add(p.id)
            todo.append((i, rows[p.id], p.answer))
    if req.task == "regex":
        for (i, ex, _), r in zip(todo, grade_regex_rows([(ex, a) for _, ex, a in todo])):
            results[i] = {"id": ex["id"], **r}
    else:
        fn = grade_cypher_row if req.task == "cypher" else grade_sql_row
        futs = [(i, ex, _POOL.submit(fn, ex, a)) for i, ex, a in todo]
        for i, ex, f in futs:
            try:
                results[i] = {"id": ex["id"], **f.result(timeout=TIMEOUT_S * 3)}
            except Exception as e:
                results[i] = {"id": ex["id"], "verdict": "error", "n_rows": 0, "error": f"judge: {type(e).__name__}"}
    graded = [r for r in results if r["verdict"] in ("correct", "wrong", "error", "empty")]
    n = len(graded)
    cnt = lambda v: sum(r["verdict"] == v for r in graded)
    summary = {
        "task": req.task, "n": n, "n_task": len(rows),
        "accuracy": round(cnt("correct") / n, 4) if n else None,
        "accuracy_full_set": round(cnt("correct") / len(rows), 4),  # missing rows count as wrong
        "correct": cnt("correct"), "wrong": cnt("wrong"), "error": cnt("error"), "empty": cnt("empty"),
        "error_rate": round(cnt("error") / n, 4) if n else None,
        "empty_rate": round(cnt("empty") / n, 4) if n else None,
        "ignored": len(results) - n, "secs": round(time.time() - t0, 2),
    }
    if req.task == "regex" and n:
        summary["soft_accuracy"] = round(sum(r.get("soft") or 0 for r in graded) / n, 4)
    return {"summary": summary, "results": results}


@app.post("/grade_one")
def grade_one(req: GradeOneReq, request: Request):
    """Ad-hoc execution: run your answer and see what it returns. No gold, no verdict."""
    rate_limit(request)
    if req.task == "cypher":
        if req.graph not in cy_exec.GRAPHS:
            raise HTTPException(400, f"graph must be one of {cy_exec.GRAPHS}")
        q = cy_score.clean_pred(req.answer)
        why = cypher_write_reason(q)
        if why:
            return JSONResponse({"ok": False, "error": why, "rows": [], "n_rows": 0}, status_code=400)
        r = _POOL.submit(cy_exec.execute, req.graph, q, TIMEOUT_S).result(timeout=TIMEOUT_S * 3)
        return {"ok": r["ok"], "query": q, "columns": r["columns"], "n_rows": len(r["rows"]),
                "rows": r["rows"][:ONE_ROWS], "truncated": len(r["rows"]) > ONE_ROWS, "error": r["error"], "secs": r["secs"]}
    if req.task == "sql":
        db = _sql_db(req.db_id or "")
        if not db:
            raise HTTPException(400, "db_id must be a Spider database id, e.g. concert_singer (see GET /tasks/sql)")
        q = sql_score.extract_sql(req.answer)
        why = sql_write_reason(q)
        if why:
            return JSONResponse({"ok": False, "error": why, "rows": [], "n_rows": 0}, status_code=400)
        r = sql_score.execute_sql(db, q, timeout=TIMEOUT_S)
        rows = r["rows"] or []
        return {"ok": r["ok"], "query": q, "n_rows": len(rows), "rows": [list(x) for x in rows[:ONE_ROWS]],
                "truncated": len(rows) > ONE_ROWS, "error": r["error"]}
    if req.task == "regex":
        strings = (req.strings or [])[:50]
        if not strings:
            raise HTTPException(400, "regex grade_one needs 'strings': a list of up to 50 strings to test")
        r = _regex_child([{"answer": req.answer, "strings": strings}], timeout=30 + 2 * len(strings))[0]
        if not r["pattern"]:
            return {"ok": False, "error": "no regex extracted"}
        if r.get("error"):
            return {"ok": False, "pattern": r["pattern"], "error": r["error"]}
        return {"ok": True, "pattern": r["pattern"],
                "results": [{"string": s, "fullmatch": m} for s, m in zip(strings, r["matches"])]}
    raise HTTPException(400, "task must be cypher, sql or regex")
