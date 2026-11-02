"""Drop-in client for The Judge. Stdlib only.
    from client import tasks, grade, run
    rows = tasks("cypher")                       # [{id, question, graph, schema, tier}, ...]
    print(grade("cypher", {r["id"]: my_model(r) for r in rows})["summary"])
"""
import json, os, urllib.request

JUDGE = os.environ.get("JUDGE_URL", "http://127.0.0.1:8787")

def _call(path, body=None):
    req = urllib.request.Request(JUDGE + path, data=json.dumps(body).encode() if body is not None else None,
                                 headers={"Content-Type": "application/json"})
    return json.load(urllib.request.urlopen(req, timeout=600))

def tasks(task):                                  # task: "cypher" | "sql" | "regex"
    return _call(f"/tasks/{task}")["rows"]

def grade(task, answers):                         # answers: {row_id: answer}; batches of 200
    items, out = [{"id": k, "answer": v} for k, v in answers.items()], []
    for i in range(0, len(items), 200):
        out += _call("/grade", {"task": task, "predictions": items[i:i + 200]})["results"]
    ok = sum(r["verdict"] == "correct" for r in out)
    return {"summary": {"n": len(out), "correct": ok, "accuracy": round(ok / max(len(out), 1), 4)}, "results": out}

def run(answer, graph="movies", task="cypher", **kw):   # ad-hoc execution, no gold
    return _call("/grade_one", {"task": task, "answer": answer, "graph": graph, **kw})
