from score import score, complexity, clean_pred

def R(cols, rows):
    return {"ok": True, "columns": cols, "rows": [dict(zip(cols, r)) for r in rows]}

G = R(["name", "n"], [["Tom", 3], ["Ann", 2]])

def test_exact_match():
    assert score(G, R(["name", "n"], [["Tom", 3], ["Ann", 2]])) == "correct"

def test_row_order_and_alias_insensitive():
    assert score(G, R(["person", "cnt"], [["Ann", 2], ["Tom", 3]])) == "correct"

def test_column_order_insensitive():
    assert score(G, R(["n", "name"], [[2, "Ann"], [3, "Tom"]])) == "correct"

def test_wrong_value_scores_wrong():
    assert score(G, R(["name", "n"], [["Tom", 4], ["Ann", 2]])) == "wrong"

def test_missing_row_wrong():
    assert score(G, R(["name", "n"], [["Tom", 3]])) == "wrong"

def test_duplicates_matter():
    assert score(G, R(["name", "n"], [["Tom", 3], ["Ann", 2], ["Ann", 2]])) == "wrong"

def test_float_normalization():
    g = R(["avg"], [[3.14159265]])
    assert score(g, R(["a"], [[3.1415]])) == "correct"
    assert score(R(["c"], [[2]]), R(["c"], [[2.0]])) == "correct"

def test_error_and_empty():
    assert score(G, {"ok": False, "rows": [], "columns": [], "error": "SyntaxError"}) == "error"
    assert score(G, R(["name", "n"], [])) == "empty"

def test_extra_column_is_wrong():
    assert score(G, R(["name", "n", "x"], [["Tom", 3, 1], ["Ann", 2, 1]])) == "wrong"

def test_collect_list_order_free():
    g = R(["l"], [[["a", "b"]]])
    assert score(g, R(["l"], [[["b", "a"]]])) == "correct"

def test_complexity():
    c = complexity("MATCH (p:Person)-[:ACTED_IN]->(m:Movie)<-[:DIRECTED]-(d) WHERE m.year > 2000 RETURN d.name, count(*) ORDER BY count(*) DESC LIMIT 5")
    assert c["hops"] == 2 and c["aggregation"] and c["where"] and c["order_by"] and c["limit"] and c["tier"] == "hard"
    assert complexity("MATCH (m:Movie {title:'X'}) RETURN m.year")["tier"] == "easy"

def test_clean_pred():
    assert clean_pred("```cypher\nMATCH (n) RETURN n;\n```") == "MATCH (n) RETURN n"
    assert clean_pred("<think>hmm</think>MATCH (n) RETURN n") == "MATCH (n) RETURN n"
    assert clean_pred(None) == ""

from score import score_lenient

def test_lenient_extra_column():
    p = R(["name", "n", "x"], [["Tom", 3, 1], ["Ann", 2, 1]])
    assert score(G, p) == "wrong" and score_lenient(G, p) == "correct"

def test_lenient_node_vs_property():
    g = R(["p"], [[{"_labels": ["Person"], "name": "Tom", "born": 1956}]])
    assert score_lenient(g, R(["name"], [["Tom"]])) == "correct"

def test_lenient_still_rejects_missing_column_and_wrong_rows():
    assert score_lenient(G, R(["name"], [["Tom"], ["Ann"]])) == "wrong"
    assert score_lenient(G, R(["name", "n"], [["Tom", 3]])) == "wrong"

def test_literal_backslash_n_2025v1():
    c = complexity(r"MATCH (p:Person)-[:ACTED_IN]->(m:Movie)\nWHERE m.released > 2000\nRETURN p.name, count(m) AS n\nORDER BY n DESC\nLIMIT 3")
    assert c["where"] and c["order_by"] and c["limit"] and c["aggregation"]
