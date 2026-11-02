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


# ---------------------------------------------------------------------------
# score_v2 (audit/SCORING.md). Every rule gets a test, and every rule gets a
# matching negative test: a rule that lets a genuinely wrong answer pass is a bug.
# ---------------------------------------------------------------------------
from score import score_v2, strip_limit, order_by_key_cols

NODE = lambda **p: {"_labels": ["Person"], **p}


def test_v2_exact_and_row_order():
    assert score_v2(G, R(["name", "n"], [["Tom", 3], ["Ann", 2]])) == "correct"
    assert score_v2(G, R(["name", "n"], [["Ann", 2], ["Tom", 3]])) == "correct"


def test_v2_ignores_column_names_and_order():
    assert score_v2(G, R(["person", "cnt"], [["Ann", 2], ["Tom", 3]])) == "correct"
    assert score_v2(G, R(["cnt", "person"], [[2, "Ann"], [3, "Tom"]])) == "correct"


def test_v2_float_rounding_and_int_float():
    assert score_v2(R(["avg"], [[3.14159265]]), R(["a"], [[3.1415926]])) == "correct"
    assert score_v2(R(["c"], [[2]]), R(["c"], [[2.0]])) == "correct"
    # ...but a different number is still wrong
    assert score_v2(R(["avg"], [[3.142]]), R(["a"], [[3.15]])) == "wrong"


def test_v2_lists_unordered():
    assert score_v2(R(["l"], [[["a", "b", "c"]]]), R(["l"], [[["c", "a", "b"]]])) == "correct"
    assert score_v2(R(["l"], [[["a", "b", "c"]]]), R(["l"], [[["a", "b"]]])) == "wrong"


def test_v2_node_vs_identifying_property():
    g = R(["p"], [[NODE(name="Tom", born=1956)], [NODE(name="Ann", born=1970)]])
    assert score_v2(g, R(["name"], [["Tom"], ["Ann"]])) == "correct"          # node -> name
    assert score_v2(R(["name"], [["Tom"]]), R(["p"], [[NODE(name="Tom")]])) == "correct"  # name -> node
    assert score_v2(g, R(["born"], [[1956], [1970]])) == "wrong"              # wrong property
    assert score_v2(g, R(["name"], [["Tom"], ["Bob"]])) == "wrong"            # different entity


def test_v2_list_vs_rows_unwrap():
    g = R(["titles"], [[["The Matrix", "Speed"]]])
    assert score_v2(g, R(["t"], [["Speed"], ["The Matrix"]])) == "correct"
    assert score_v2(g, R(["t"], [["Speed"], ["The Matrix"], ["Heat"]])) == "wrong"


def test_v2_limit_without_order_by_accepts_any_valid_slice():
    gold_c = "MATCH (m:Movie) RETURN m.title AS t LIMIT 2"
    gold = R(["t"], [["A"], ["B"]])
    unl = R(["t"], [["A"], ["B"], ["C"], ["D"]])
    assert score_v2(gold, R(["t"], [["C"], ["D"]]), gold_c, unl) == "correct"
    assert score_v2(gold, R(["t"], [["C"], ["D"], ["A"]]), gold_c, unl) == "wrong"   # wrong size
    assert score_v2(gold, R(["t"], [["C"], ["Z"]]), gold_c, unl) == "wrong"          # not in result
    assert score_v2(gold, R(["t"], [["C"], ["D"]]), gold_c, None) == "wrong"         # no unlimited: strict


def test_v2_limit_with_order_by_only_accepts_boundary_ties():
    gold_c = "MATCH (a:Actor) RETURN a.name AS actor, a.n AS n ORDER BY n DESC LIMIT 3"
    gold = R(["actor", "n"], [["Kurt", 17], ["Brad", 17], ["Ewan", 16]])
    unl = R(["actor", "n"], [["Kurt", 17], ["Brad", 17], ["Johnny", 17], ["Ewan", 16], ["Sam", 2]])
    # swapping a tied 17 for another 17 is a legitimate output of the gold query itself
    assert score_v2(gold, R(["actor", "n"], [["Kurt", 17], ["Johnny", 17], ["Ewan", 16]]), gold_c, unl) == "correct"
    # a different sort-key multiset is NOT a valid top-3
    assert score_v2(gold, R(["actor", "n"], [["Kurt", 17], ["Brad", 17], ["Johnny", 17]]), gold_c, unl) == "wrong"
    assert score_v2(gold, R(["actor", "n"], [["Ewan", 16], ["Sam", 2], ["Kurt", 17]]), gold_c, unl) == "wrong"


def test_v2_must_still_be_wrong():
    assert score_v2(G, R(["name", "n"], [["Tom", 4], ["Ann", 2]])) == "wrong"        # wrong aggregate
    assert score_v2(G, R(["name", "n"], [["Tom", 3]])) == "wrong"                    # missing row
    assert score_v2(G, R(["name", "n"], [["Tom", 3], ["Ann", 2], ["Ann", 2]])) == "wrong"  # dup
    assert score_v2(G, R(["name", "n", "x"], [["Tom", 3, 1], ["Ann", 2, 1]])) == "wrong"   # extra column
    assert score_v2(G, R(["name"], [["Tom"], ["Ann"]])) == "wrong"                   # missing column
    assert score_v2(G, R(["name", "n"], [])) == "empty"                              # empty vs rows
    assert score_v2(G, {"ok": False, "rows": [], "columns": [], "error": "SyntaxError"}) == "error"


def test_v2_empty_gold_only_matched_by_empty():
    g = R(["x"], [])
    assert score_v2(g, R(["x"], [])) == "correct"
    assert score_v2(g, R(["x"], [["anything"]])) == "wrong"


def test_v2_limit_rule_does_not_rescue_a_wrong_query():
    # right size, rows inside the unlimited gold result, but gold has no LIMIT at all
    gold_c = "MATCH (m:Movie) WHERE m.year = 1999 RETURN m.title AS t"
    gold = R(["t"], [["A"], ["B"]])
    unl = R(["t"], [["A"], ["B"], ["C"]])
    assert score_v2(gold, R(["t"], [["B"], ["C"]]), gold_c, unl) == "wrong"


def test_strip_limit_and_order_by_cols():
    assert strip_limit("MATCH (n) RETURN n ORDER BY n.a DESC LIMIT 5") == "MATCH (n) RETURN n ORDER BY n.a DESC"
    assert "LIMIT" not in strip_limit(r"MATCH (n) RETURN n\nLIMIT 10").upper()
    assert order_by_key_cols("... ORDER BY genreCount DESC LIMIT 5", ["actor", "genreCount"]) == ["genreCount"]
    assert order_by_key_cols("... ORDER BY m.year LIMIT 5", ["title", "year"]) == ["year"]
    assert order_by_key_cols("... ORDER BY rand() LIMIT 5", ["title"]) == []   # unresolvable -> stay strict


def test_v2_null_sort_key_is_not_a_tie():
    """A NULL ORDER BY key means the gold ordering is meaningless, not that rows tie.
    Crediting a different query for landing in the NULL region would flatter us."""
    gold_c = "MATCH (m:Movie) RETURN m.title AS t, m.imdbRating AS r ORDER BY r DESC LIMIT 3"
    gold = R(["t", "r"], [["A", None], ["B", None], ["C", None]])
    unl = R(["t", "r"], [["A", None], ["B", None], ["C", None], ["D", None], ["E", None]])
    assert score_v2(gold, R(["t", "r"], [["A", None], ["D", None], ["E", None]]), gold_c, unl) == "wrong"


def test_v2_genuine_all_equal_tie_is_accepted():
    """All sort keys equal and non-null: the gold query's own top-k really is arbitrary."""
    gold_c = "MATCH (p:Person) RETURN p.name AS n, p.f AS f ORDER BY f DESC LIMIT 2"
    gold = R(["n", "f"], [["A", 0], ["B", 0]])
    unl = R(["n", "f"], [["A", 0], ["B", 0], ["C", 0], ["D", 0]])
    assert score_v2(gold, R(["n", "f"], [["C", 0], ["D", 0]]), gold_c, unl) == "correct"


def test_v2_identifier_search_is_restricted_to_id_like_properties():
    g = R(["f"], [[{"_labels": ["Filing"], "sar_id": "3146", "amount": 665000}]])
    assert score_v2(g, R(["sar"], [["3146"]])) == "correct"       # node <-> sar_id
    assert score_v2(g, R(["amt"], [[665000]])) == "wrong"         # amount is not an identifier
