"""Offline tests for retrieve.py, fixes.py and metrics.py (no network, no model calls)."""
import fixes, metrics
from retrieve import Retriever

MOVIES = """Node properties:
- **Movie**
  - `title`: STRING Example: "The Matrix"
  - `released`: INTEGER Min: 1975, Max: 2012
- **Person**
  - `name`: STRING Example: "Keanu Reeves"
Relationship properties:
- **ACTED_IN**
  - `roles: LIST` Min Size: 1, Max Size: 6
The relationships:
(:Person)-[:ACTED_IN]->(:Movie)
(:Person)-[:FOLLOWS]->(:Person)
"""


# ---------- retrieve ----------
def test_retriever_prefers_shared_words_and_stays_in_graph():
    pool = [{"id": "a", "graph": "movies", "question": "Who acted in The Matrix?", "cypher": "q1"},
            {"id": "b", "graph": "movies", "question": "How many movies were released in 1999?", "cypher": "q2"},
            {"id": "c", "graph": "northwind", "question": "Who acted in The Matrix?", "cypher": "q3"}]
    top = Retriever(pool).top("Which actors acted in The Matrix Reloaded?", "movies", 1)
    assert [r["id"] for r in top] == ["a"]


def test_retriever_never_returns_the_question_itself():
    pool = [{"id": "a", "graph": "movies", "question": "Who acted in The Matrix?", "cypher": "q1"},
            {"id": "b", "graph": "movies", "question": "Who directed The Matrix?", "cypher": "q2"}]
    r = Retriever(pool)
    assert [x["id"] for x in r.top("Who acted in The Matrix?", "movies", 5)] == ["b"]  # same text skipped
    assert [x["id"] for x in r.top("anything", "movies", 5, exclude_ids={"a"})] == ["b"]


# ---------- schema parsing ----------
def test_schema_parsing():
    assert fixes.relationships(MOVIES) == {("Person", "ACTED_IN", "Movie"), ("Person", "FOLLOWS", "Person")}
    names = fixes.schema_names(MOVIES)
    assert names["labels"] == {"Movie", "Person"}
    assert names["types"] == {"ACTED_IN", "FOLLOWS"}
    assert {"title", "released", "name", "roles"} <= names["props"]


# ---------- arrow fix ----------
def test_flip_wrong_direction_inline_labels():
    q = "MATCH (m:Movie)-[:ACTED_IN]->(p:Person) RETURN p.name"
    assert fixes.flip_arrows(q, MOVIES) == "MATCH (m:Movie)<-[:ACTED_IN]-(p:Person) RETURN p.name"


def test_flip_uses_labels_declared_elsewhere_in_query():
    q = "MATCH (p:Person), (m:Movie) MATCH (m)-[r:ACTED_IN]->(p) RETURN count(*)"
    assert fixes.flip_arrows(q, MOVIES) == "MATCH (p:Person), (m:Movie) MATCH (m)<-[r:ACTED_IN]-(p) RETURN count(*)"


def test_flip_leaves_correct_undirected_and_symmetric_patterns_alone():
    for q in ["MATCH (p:Person)-[:ACTED_IN]->(m:Movie) RETURN m",       # already right
              "MATCH (m:Movie)-[:ACTED_IN]-(p:Person) RETURN p",        # undirected
              "MATCH (a:Person)<-[:FOLLOWS]-(b:Person) RETURN a",       # declared both ways (Person->Person)
              "MATCH (x)-[:ACTED_IN]->(y) RETURN x"]:                    # labels unknown
        assert fixes.flip_arrows(q, MOVIES) == q


def test_flip_every_hop_in_a_chain():
    q = "MATCH (m:Movie)-[:ACTED_IN]->(p:Person)-[:ACTED_IN]->(m2:Movie) RETURN m2"
    assert fixes.flip_arrows(q, MOVIES) == "MATCH (m:Movie)<-[:ACTED_IN]-(p:Person)-[:ACTED_IN]->(m2:Movie) RETURN m2"


# ---------- hints ----------
def test_schema_hints_name_what_is_missing():
    q = "MATCH (p:Actor)-[:STARRED_IN]->(m:Movie) WHERE m.year = 1999 AND m.title <> 'p.fake' RETURN p.name"
    hints = fixes.schema_hints(q, MOVIES)
    assert hints == ["The schema has no label named Actor.", "The schema has no relationship type named STARRED_IN.",
                     "The schema has no property named year."]


def test_schema_hints_ignore_function_namespaces_and_numbers():
    q = "MATCH (m:Movie) RETURN apoc.coll.sum([1.5, 2.0]) AS s, date.truncate('year', date()) AS d"
    assert fixes.schema_hints(q, MOVIES) == []


def test_value_lookups_for_both_literal_styles():
    q = "MATCH (p:Person {name: \"Tom Hank\"})-[:ACTED_IN]->(m:Movie) WHERE m.title = 'Matrix' RETURN m"
    found = {(label, prop, value) for label, prop, value, _ in fixes.value_lookups(q)}
    assert found == {("Person", "name", "Tom Hank"), ("Movie", "title", "Matrix")}
    lookup = fixes.value_lookups("MATCH (m:Movie) WHERE m.title = 'Matrix' RETURN m")[0][3]
    assert lookup == ("MATCH (n:`Movie`) WHERE toLower(toString(n.`title`)) CONTAINS 'matrix' "
                      "RETURN DISTINCT n.`title` AS value LIMIT 5")


# ---------- metrics: cutting a trace at a stage ----------
def attempt(source, status, outcome, cost=0.01, secs=1.0, calls=1):
    return {"source": source, "status": status, "outcome": outcome, "cypher": source, "cost": cost, "secs": secs,
            "calls": calls}


def test_cut_returns_what_each_shorter_config_would_have_returned():
    row = {"attempts": [attempt("first", "empty", "empty"), attempt("fix", "empty", "empty", cost=0, calls=0),
                        attempt("repair1", "error", "error"), attempt("repair2", "rows", "correct"),
                        attempt("escalate:first", "rows", "wrong")]}  # never happens in practice; checks the order
    assert metrics.cut(row, "first")["outcome"] == "empty"
    assert metrics.cut(row, "fix") == {"outcome": "empty", "stage": "fix", "cypher": "fix", "cost": 0.01,
                                       "secs": 2.0, "calls": 1}
    assert metrics.cut(row, "repair")["outcome"] == "correct"
    assert metrics.cut(row, "repair")["calls"] == 3


def test_cut_prefers_the_last_attempt_that_returned_rows():
    row = {"attempts": [attempt("first", "rows", "wrong"), attempt("escalate:first", "error", "error")]}
    assert metrics.cut(row, "escalate")["outcome"] == "wrong"


def test_summary_counts_and_interval():
    rows = [{"graph": "movies", "tier": "easy", "attempts": [attempt("first", "rows", "correct")]},
            {"graph": "movies", "tier": "hard", "attempts": [attempt("first", "empty", "empty")]}]
    s = metrics.summarize(rows, "first")
    assert (s["n"], s["correct"], s["accuracy"]) == (2, 1, 0.5)
    assert s["by_tier"] == {"easy": 1.0, "hard": 0.0}
    assert s["by_stage"]["first"] == 1 and s["by_stage"]["wrong"] == 1
    lo, hi = s["ci95"]
    assert lo < 0.5 < hi


# ---------- compare ----------
def test_compare_paired_difference_and_mcnemar():
    import compare
    a = {"q1": True, "q2": False, "q3": False, "q4": True}
    b = {"q1": True, "q2": True, "q3": True, "q4": True}
    r = compare.compare(a, b, resamples=200)
    assert (r["n"], r["diff"], r["only_a"], r["only_b"]) == (4, 0.5, 0, 2)
    assert r["p_mcnemar"] == 0.5            # 2 discordant pairs, both favour B: p = 2 * (1/4)
    assert compare.mcnemar_p(0, 0) == 1.0


def test_cut_falls_back_to_warned_rows_when_no_clean_rows():
    row = {"attempts": [attempt("first", "warn", "correct"), attempt("repair1", "error", "error")]}
    assert metrics.cut(row, "repair")["outcome"] == "correct"   # warned rows beat an error
    row["attempts"].append(attempt("repair2", "rows", "wrong"))
    assert metrics.cut(row, "repair")["outcome"] == "wrong"     # a clean answer beats a warned one


# ---------- build_sft ----------
def test_repair_examples_replay_the_conversation_that_led_to_the_fix():
    import build_sft
    pool = [{"id": "ex1", "graph": "movies", "question": "Who acted in X?", "cypher": "MATCH 1"}]
    row = {"id": "p1", "graph": "movies", "question": "Who directed Y?", "schema": MOVIES, "cypher": "GOLD"}
    run = {"split": "train", "rows": [{
        "id": "p1", "outcome": "correct", "final_cypher": "GOOD", "examples": ["ex1"],
        "attempts": [{"source": "first", "model": "m", "output": "BAD1", "cypher": "BAD1", "feedback": "no rows"},
                     {"source": "repair1", "model": "m", "output": "GOOD", "cypher": "GOOD"}]}]}
    out = list(build_sft.traces([row], run, Retriever(pool), with_repairs=True))
    assert [e["source"] for e in out] == ["trace", "repair"]
    assert out[0]["answer"] == "GOOD" and len(out[0]["messages"]) == 2          # first prompt -> fixed query
    assert [m["content"] for m in out[1]["messages"][2:]] == ["BAD1", "no rows"]  # replayed repair turn
    assert "Who acted in X?" in out[0]["messages"][1]["content"]                 # same retrieved example


def test_without_warn_stops_at_the_first_query_with_rows():
    row = {"attempts": [attempt("first", "warn", "wrong"), attempt("repair1", "rows", "correct")]}
    assert metrics.cut(row, "repair")["outcome"] == "correct"                       # --warn on: repaired
    assert metrics.cut(metrics.without_warn(row), "repair")["outcome"] == "wrong"   # --warn off: stops at first
    assert metrics.cut(metrics.without_warn(row), "repair")["calls"] == 1


def test_distill_takes_one_verified_answer_per_question_earlier_runs_first():
    import build_sft
    pool = [{"id": "ex1", "graph": "movies", "question": "Who acted in X?", "cypher": "MATCH 1"}]
    rows = [{"id": q, "graph": "movies", "question": f"q {q}", "schema": MOVIES, "cypher": "GOLD"} for q in ("a", "b", "c")]
    run = lambda model, solved: {"split": "train", "model": f"accounts/fireworks/models/{model}", "rows": [
        {"id": q, "outcome": "correct" if q in solved else "wrong", "final_cypher": f"{model}-{q}", "examples": ["ex1"]}
        for q in ("a", "b", "c")]}
    out = list(build_sft.distill(rows, [run("student", {"a"}), run("teacher", {"a", "b"})], Retriever(pool)))
    assert [(e["id"], e["answer"]) for e in out] == [("a", "student-a"), ("b", "teacher-b")]   # c: nobody solved it


def test_teacher_examples_only_where_the_student_failed():
    import build_sft
    pool = [{"id": "ex1", "graph": "movies", "question": "Who acted in X?", "cypher": "MATCH 1"}]
    rows = [{"id": q, "graph": "movies", "question": f"q {q}", "schema": MOVIES, "cypher": "GOLD"} for q in ("a", "b")]
    run = lambda model, solved: {"split": "train", "model": f"m/{model}", "rows": [
        {"id": q, "outcome": "correct" if q in solved else "wrong", "final_cypher": f"{model}-{q}", "examples": ["ex1"]}
        for q in ("a", "b")]}
    out = list(build_sft.teacher(rows, run("student", {"a"}), run("kimi", {"a", "b"}), Retriever(pool)))
    assert [(e["id"], e["answer"], e["source"]) for e in out] == [("b", "kimi-b", "distill:kimi")]
