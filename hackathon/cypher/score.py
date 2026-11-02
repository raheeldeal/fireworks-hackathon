"""Execution-based scoring for text-to-Cypher.

score(gold_result, pred_result, gold_cypher) -> "correct" | "wrong" | "error" | "empty"
Results are executor.execute() dicts. Rows compared as unordered multisets. Column names ignored
(models rename aliases freely). Column order ignored when the gold query has no ORDER BY; with ORDER BY
the row order is still not enforced (ties make it brittle) but the LIMIT-selected set must match.
Floats rounded to 3 decimals; 2 == 2.0.
"""
import json, re
from collections import Counter

FLOAT_DP = 3


def norm(v):
    if isinstance(v, bool) or v is None or isinstance(v, str):
        return v
    if isinstance(v, (int, float)):
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


def _unescape(cypher):
    # text2cypher-2025v1 writes line breaks as a literal backslash + n; see executor.normalize_cypher
    return (cypher or "").replace("\\n", "\n")


def has_order_by(cypher):
    return bool(re.search(r"\border\s+by\b", _unescape(cypher), re.I))


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


AGG = re.compile(r"\b(count|sum|avg|min|max|collect|stdev|percentile\w*)\s*\(", re.I)
REL = re.compile(r"<?-\[[^\]]*\]->?|<--|-->|(?<=\))--(?=\()")


def complexity(cypher):
    c = _unescape(cypher)
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


def _flat(v, out):
    """Flatten a value into scalar tokens; nodes/maps contribute their property values."""
    if isinstance(v, dict):
        for k, x in v.items():
            if not k.startswith("_"):
                _flat(x, out)
    else:
        out.append(repr(norm(v)))
    return out


def _row_tokens(row):
    vals = row.values() if isinstance(row, dict) else row
    has_node = any(isinstance(v, dict) for v in vals)
    toks = []
    for v in vals:
        _flat(v, toks)
    return set(toks), has_node


def score_lenient(gold, pred, gold_cypher=""):
    """Secondary metric. Same as score(), but a row also matches when the prediction returns extra
    columns (gold values are a subset of pred values), or when gold returned whole nodes and the
    prediction returned some of their properties. Row counts must still match exactly."""
    s = score(gold, pred, gold_cypher)
    if s != "wrong":
        return s
    g = [_row_tokens(r) for r in gold["rows"]]
    p = [_row_tokens(r)[0] for r in pred["rows"]]
    if len(g) != len(p):
        return "wrong"
    used = [False] * len(p)
    for gt, gnode in sorted(g, key=lambda x: -len(x[0])):
        hit = False
        for i, pt in enumerate(p):
            if used[i] or not pt:
                continue
            if gt <= pt or (gnode and pt <= gt):
                used[i] = hit = True
                break
        if not hit:
            return "wrong"
    return "correct"
