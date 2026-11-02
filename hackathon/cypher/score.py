"""Execution-based scoring for text-to-Cypher.

score(gold_result, pred_result, gold_cypher) -> "correct" | "wrong" | "error" | "empty"
Results are executor.execute() dicts. Rows compared as unordered multisets. Column names ignored
(models rename aliases freely). Column order ignored when the gold query has no ORDER BY; with ORDER BY
the row order is still not enforced (ties make it brittle) but the LIMIT-selected set must match.
Floats rounded to 3 decimals; 2 == 2.0.
"""
import json, math, re
from collections import Counter

FLOAT_DP = 3


def norm(v):
    if isinstance(v, bool) or v is None or isinstance(v, str):
        return v
    if isinstance(v, (int, float)):
        if not math.isfinite(v):  # NaN / inf (e.g. an average over nothing): compare by name, int() would crash
            return repr(float(v))
        f = round(float(v), FLOAT_DP)
        return int(f) if f == int(f) else f
    if isinstance(v, (list, tuple)):
        return tuple(sorted((norm(x) for x in v), key=repr))  # lists from collect() are order-free
    if isinstance(v, dict):
        return tuple(sorted((k, norm(x)) for k, x in v.items()))
    return repr(v)


def row_key(row, columns, keep_col_order):
    vals = [norm(row[c]) for c in columns] if isinstance(row, dict) else [norm(x) for x in row]
    if not keep_col_order:
        vals = sorted(vals, key=repr)
    return tuple(vals)


def has_order_by(cypher):
    return bool(re.search(r"\border\s+by\b", cypher or "", re.I))


def score(gold, pred, gold_cypher=""):
    if not pred.get("ok"):
        return "error"
    if not pred["rows"]:
        return "empty" if gold["rows"] else "correct"
    keep = has_order_by(gold_cypher)
    gk = Counter(row_key(r, gold["columns"], keep) for r in gold["rows"])
    pk = Counter(row_key(r, pred["columns"], keep) for r in pred["rows"])
    if gk == pk:
        return "correct"
    if keep:  # column order differs from gold but content identical
        gk2 = Counter(row_key(r, gold["columns"], False) for r in gold["rows"])
        pk2 = Counter(row_key(r, pred["columns"], False) for r in pred["rows"])
        if gk2 == pk2:
            return "correct"
    return "wrong"


def covers_gold(gold, pred):
    """Lenient companion metric, never the headline: same number of rows, and every gold row's values appear in a
    distinct predicted row (extra columns allowed). Counts e.g. returning title *and* rating when gold returns title.
    Matching is greedy, so it can only under-count."""
    if not pred.get("ok") or len(pred["rows"]) != len(gold["rows"]) or not gold["rows"]:
        return False
    values = lambda r, cols: Counter(norm(r[c]) for c in cols) if isinstance(r, dict) else Counter(norm(x) for x in r)
    pred_rows = [values(r, pred["columns"]) for r in pred["rows"]]
    used = set()
    for g in (values(r, gold["columns"]) for r in gold["rows"]):
        j = next((j for j, p in enumerate(pred_rows) if j not in used and not g - p), None)
        if j is None:
            return False
        used.add(j)
    return True


AGG = re.compile(r"\b(count|sum|avg|min|max|collect|stdev|percentile\w*)\s*\(", re.I)
REL = re.compile(r"<?-\[[^\]]*\]->?|<--|-->|(?<=\))--(?=\()")


def complexity(cypher):
    c = cypher or ""
    rels = REL.findall(c)
    varlen = any("*" in r for r in rels)
    hops = len(rels) + (1 if varlen else 0)
    agg = bool(AGG.search(c))
    where = bool(re.search(r"\bwhere\b", c, re.I)) or bool(re.search(r"\(\w*:\w+\s*\{", c))
    order = has_order_by(c)
    limit = bool(re.search(r"\blimit\b", c, re.I))
    multi = hops >= 2
    if multi and agg:
        tier = "hard"
    elif multi or agg:
        tier = "medium"
    else:
        tier = "easy"
    return {"hops": hops, "var_length": varlen, "aggregation": agg, "where": where,
            "order_by": order, "limit": limit, "multi_hop": multi, "tier": tier}


def clean_pred(text):
    """Pull a Cypher query out of model output: drop think blocks, code fences, leading labels."""
    if not text:
        return ""
    if "</think>" in text:
        text = text.split("</think>")[-1]
    m = re.search(r"```(?:cypher|sql)?\s*(.*?)```", text, re.S | re.I)
    if m:
        text = m.group(1)
    text = text.strip().strip("`").strip()
    text = re.sub(r"^(cypher|query)\s*:\s*", "", text, flags=re.I)
    return text.strip().rstrip(";").strip()
