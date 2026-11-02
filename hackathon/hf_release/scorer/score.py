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


# ---------------------------------------------------------------------------
# score_v2: execution accuracy with result-set equality, the standard used by
# published text-to-Cypher / text-to-SQL evaluations. Rules documented one by
# one in audit/SCORING.md. score() and score_lenient() above are unchanged so
# the three can be compared on the same runs.
# ---------------------------------------------------------------------------

ID_PROPS = ("name", "title", "id")  # identifying properties, in priority order

LIMIT_RE = re.compile(r"\s+\blimit\s+\d+\b", re.I)
SKIP_RE = re.compile(r"\s+\bskip\s+\d+\b", re.I)


def strip_limit(cypher):
    """The same query with every LIMIT (and SKIP) clause removed: the full result the gold
    query was truncating. Used only to test containment for LIMIT rows."""
    c = _unescape(cypher or "")
    return SKIP_RE.sub(" ", LIMIT_RE.sub(" ", c)).strip()


def has_limit(cypher):
    return bool(re.search(r"\blimit\s+\d+\b", _unescape(cypher or ""), re.I))


def order_by_key_cols(cypher, columns):
    """Columns of the result that the gold query's final ORDER BY sorts on, if we can tell.
    Returns [] when the ORDER BY expression does not resolve to a returned column, in which
    case the tie rule is not applied at all (we stay strict rather than guess)."""
    c = _unescape(cypher or "")
    m = None
    for m2 in re.finditer(r"\border\s+by\b(.*?)(?=\blimit\b|\bskip\b|\breturn\b|\bwith\b|\bmatch\b|$)", c, re.I | re.S):
        m = m2
    if not m:
        return []
    cols, lower = [], {str(x).lower(): x for x in columns}
    for term in m.group(1).split(","):
        t = term.strip().rstrip(";")
        t = re.sub(r"\b(asc|ascending|desc|descending)\b\s*$", "", t, flags=re.I).strip()
        if not t:
            continue
        cand = [t.lower()]
        if "." in t:
            cand.append(t.split(".")[-1].lower())
        hit = next((lower[x] for x in cand if x in lower), None)
        if hit is None:
            return []  # an ORDER BY term we cannot map to a column -> no tie relaxation
        cols.append(hit)
    return cols


def _is_entity(v):
    return isinstance(v, dict) and ("_labels" in v or "_type" in v)


def _ident_candidates(res):
    """Identifier-like property names present on the node/relationship objects in a result,
    most canonical first: name, title, id, then any *id / *_id key (movieId, sar_id, ...).
    Only identifier-like names, so a plain data property (m.year) is never an identity."""
    seen = []
    for r in res["rows"]:
        for v in _vals(r, res.get("columns") or []):
            if not _is_entity(v):
                continue
            for k in v:
                if k.startswith("_") or k in seen:
                    continue
                kl = k.lower()
                if kl in ID_PROPS or kl.endswith("id") or kl.endswith("_id"):
                    seen.append(k)
    return sorted(seen, key=lambda k: (ID_PROPS.index(k.lower()) if k.lower() in ID_PROPS else 9, k))


def _ident(v, prefer=None):
    """Reduce a node/relationship to its identifying property so that `RETURN m` and
    `RETURN m.title` describe the same set of entities. Non-entities pass through."""
    if not _is_entity(v):
        return norm(v)
    for p in ([prefer] if prefer else []) + list(ID_PROPS):
        if p and p in v:
            return norm(v[p])
    for k in v:  # <label>Id style keys, e.g. movieId, userId
        if k.lower().endswith("id") and not k.startswith("_"):
            return norm(v[k])
    return norm(v)


def _vals(row, columns):
    if isinstance(row, dict):
        cols = columns if columns and all(c in row for c in columns) else list(row.keys())
        return [row[c] for c in cols]
    return list(row)


def _rowkey(row, columns, ident=False, prefer=None):
    """One row as an order-free key: column order ignored (values sorted), column names ignored."""
    vals = [(_ident(v, prefer) if ident else norm(v)) for v in _vals(row, columns)]
    return tuple(sorted(vals, key=repr))


def _bag(res, ident=False, prefer=None):
    return Counter(_rowkey(r, res.get("columns") or [], ident, prefer) for r in res["rows"])


def _flat_scalars(res):
    """Rows as a flat multiset of scalars, used only for the list-vs-rows equivalence:
    one row holding collect(x) vs N single-column rows of x answer the same question."""
    out = []
    for r in res["rows"]:
        for v in _vals(r, res.get("columns") or []):
            if isinstance(v, (list, tuple)):
                out.extend(_ident(x) for x in v)
            else:
                out.append(_ident(v))
    return Counter(out)


def _single_col_or_list(res):
    """True when the result is either N single-column rows, or one row whose single column is
    a list. Only then is the list-vs-rows unwrap allowed."""
    rows = res["rows"]
    if not rows:
        return False
    widths = {len(_vals(r, res.get("columns") or [])) for r in rows}
    if widths != {1}:
        return False
    if len(rows) == 1:
        return True
    return not any(isinstance(_vals(r, res.get("columns") or [])[0], (list, tuple)) for r in rows)


def _sub_multiset(small, big):
    return all(big.get(k, 0) >= n for k, n in small.items())


def score_v2(gold, pred, gold_cypher="", gold_unlimited=None):
    """Execution accuracy. `gold_unlimited` is the executed result of strip_limit(gold_cypher),
    required only to judge LIMIT rows; without it those rows are judged strictly."""
    if not pred.get("ok"):
        return "error"
    if not pred["rows"]:
        return "correct" if not gold["rows"] else "empty"
    if not gold["rows"]:
        return "wrong"

    gb, pb = _bag(gold), _bag(pred)
    if gb == pb:
        return "correct"                                            # R1-R6

    # R7 node <-> identifying property. Try each identifier-like property present, and accept if
    # ANY single consistent choice makes the two results equal. Applied uniformly to both sides,
    # and restricted to identifier-like names, so projecting a data property (m.year) never matches.
    for prefer in [None] + _ident_candidates(gold) + _ident_candidates(pred):
        if _bag(gold, True, prefer) == _bag(pred, True, prefer):
            return "correct"

    if _single_col_or_list(gold) and _single_col_or_list(pred):     # R8 list <-> rows
        if _flat_scalars(gold) == _flat_scalars(pred):
            return "correct"

    # R9 LIMIT non-determinism: the gold query itself may legitimately return other rows.
    if has_limit(gold_cypher) and gold_unlimited and gold_unlimited.get("ok") and gold_unlimited["rows"]:
        if len(pred["rows"]) == len(gold["rows"]):
            inside = _sub_multiset(pb, _bag(gold_unlimited))
            for prefer in ([None] + _ident_candidates(gold_unlimited) + _ident_candidates(pred)) \
                    if not inside else []:
                if _sub_multiset(_bag(pred, True, prefer), _bag(gold_unlimited, True, prefer)):
                    inside = True
                    break
            if inside:
                keys = order_by_key_cols(gold_cypher, gold.get("columns") or [])
                if not has_order_by(gold_cypher):
                    return "correct"                                # no ORDER BY: any such set is valid
                if keys and not any(r.get(c) is None for r in gold["rows"] for c in keys):
                    # a NULL sort key means the gold ordering is meaningless, not a tie: stay strict
                    gk = Counter(tuple(norm(r[c]) for c in keys) for r in gold["rows"]
                                 if all(c in r for c in keys))
                    pcols = order_by_key_cols(gold_cypher, pred.get("columns") or [])
                    pk = None
                    if len(gk) and pcols and len(pcols) == len(keys):
                        pk = Counter(tuple(norm(r[c]) for c in pcols) for r in pred["rows"]
                                     if all(c in r for c in pcols))
                    else:  # aliases differ: fall back to positional sort-key match on the unlimited rows
                        ug = {_rowkey(r, gold_unlimited.get("columns") or [], True):
                              tuple(norm(r[c]) for c in keys) for r in gold_unlimited["rows"]
                              if all(c in r for c in keys)}
                        if ug:
                            pk = Counter(ug.get(k) for k in
                                         [_rowkey(r, pred.get("columns") or [], True) for r in pred["rows"]])
                            if None in pk:
                                pk = None
                    if pk is not None and gk and gk == pk:
                        return "correct"                            # ties at the LIMIT boundary only
    return "wrong"
