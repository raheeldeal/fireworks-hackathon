"""Checks that need no model call: arrow-direction fix, schema hints, and value-lookup queries.

All functions are pure string work on the query and the schema text, so they are unit-tested offline.
The schema text format is the dataset's: a "Node properties:" list of `- **Label**` entries with backticked
property names, a "Relationship properties:" list, and a "The relationships:" list of `(:A)-[:TYPE]->(:B)`.
"""
import re

REL_LINE = re.compile(r"\(:(\w+)\)-\[:(\w+)\]->\(:(\w+)\)")
# One node pattern, e.g. `(m:Movie {title: 'X'})` or `(m)` or `()`. Captures variable and first label.
NODE = r"\(\s*(\w*)\s*(?::\s*`?(\w+)`?)?[^()]*\)"
# node, arrow, node. The right node sits in a lookahead so chains like (a)-[]->(b)-[]->(c) match every hop.
HOP = re.compile(NODE + r"\s*(<?-\s*\[\s*\w*\s*:\s*`?(\w+)`?[^\]]*\]\s*->?)\s*(?=" + NODE + ")")
STRING = re.compile(r"'(?:[^'\\]|\\.)*'|\"(?:[^\"\\]|\\.)*\"")
FUNC_NAMESPACES = {"apoc", "gds", "date", "datetime", "duration", "point", "localdatetime", "time", "db", "math"}


# ---------- reading the schema ----------
def relationships(schema):
    """Set of (source_label, TYPE, target_label) triples the schema declares."""
    return set(REL_LINE.findall(schema))


def schema_names(schema):
    """Labels, relationship types and property names that appear in the schema."""
    rels = relationships(schema)
    labels = set(re.findall(r"- \*\*(\w+)\*\*", schema.split("Relationship properties:")[0]))
    labels |= {a for a, _, _ in rels} | {b for _, _, b in rels}
    types = {t for _, t, _ in rels}
    props = set(re.findall(r"`(\w+)", schema))
    return {"labels": labels, "types": types, "props": props}


# ---------- reading the query ----------
def strip_strings(cypher):
    return STRING.sub("''", cypher)


def var_labels(cypher):
    """Map each node variable to the first label it is given anywhere in the query, e.g. {'m': 'Movie'}."""
    out = {}
    for var, label in re.findall(r"\(\s*(\w+)\s*:\s*`?(\w+)`?", strip_strings(cypher)):
        out.setdefault(var, label)
    return out


# ---------- fix 1: arrow direction ----------
def flip_arrows(cypher, schema):
    """Reverse any typed, directed relationship whose direction the schema declares only the other way round.

    Returns the fixed query, or the original if nothing needed flipping. Undirected patterns, unknown labels and
    multi-type patterns ([:A|B]) are left alone.
    """
    rels = relationships(schema)
    labels = var_labels(cypher)
    edits = []
    for m in HOP.finditer(cypher):
        left_var, left_label, arrow, rtype, right_var, right_label = m.groups()
        left = left_label or labels.get(left_var)
        right = right_label or labels.get(right_var)
        pointing_right, pointing_left = arrow.rstrip().endswith(">"), arrow.lstrip().startswith("<")
        if not left or not right or pointing_right == pointing_left:
            continue  # unknown label, or undirected
        src, dst = (left, right) if pointing_right else (right, left)
        if (src, rtype, dst) not in rels and (dst, rtype, src) in rels:
            body = arrow.strip().lstrip("<").rstrip(">")  # "-[r:T]-"
            edits.append((m.start(3), m.end(3), body + ">" if pointing_left else "<" + body))
    for start, end, new in sorted(edits, reverse=True):  # apply right to left so offsets stay valid
        cypher = cypher[:start] + new + cypher[end:]
    return cypher


# ---------- fix 2: hints for the repair prompt ----------
def schema_hints(cypher, schema):
    """Plain-English notes on labels, relationship types and properties the query uses but the schema lacks."""
    names, q = schema_names(schema), strip_strings(cypher)
    used_labels = set(re.findall(r"\(\s*\w*\s*:\s*`?(\w+)`?", q))
    used_types = {t for group in re.findall(r"\[\s*\w*\s*:\s*([\w|`:]+)", q) for t in re.split(r"[|:`]+", group) if t}
    used_props = {p for ns, p in re.findall(r"\b([A-Za-z_]\w*)\.([A-Za-z_]\w*)\b", q) if ns.lower() not in FUNC_NAMESPACES}
    hints = []
    for kind, used, known in (("label", used_labels, names["labels"]), ("relationship type", used_types, names["types"]),
                              ("property", used_props, names["props"])):
        missing = sorted(used - known)
        if missing:
            hints.append(f"The schema has no {kind} named {', '.join(missing)}.")
    return hints


def value_lookups(cypher):
    """For each string literal compared to a property of a labelled node, a read-only query listing similar
    stored values. Returns [(label, prop, value, lookup_cypher)]."""
    labels, out = var_labels(cypher), []
    lit = r"""['"]([^'"\\]{2,60})['"]"""                                                 # 'X' or "X"
    pairs = re.findall(r"\b(\w+)\.(\w+)\s*=\s*" + lit, cypher)                          # m.title = 'X'
    pairs += [(var, p, v) for var, body in re.findall(r"\(\s*(\w+)\s*:\s*\w+\s*\{([^}]*)\}", cypher)
              for p, v in re.findall(r"(\w+)\s*:\s*" + lit, body)]                       # (m:Movie {title: 'X'})
    for var, prop, value in pairs:
        if var in labels:
            needle = value.lower().replace("'", "")
            q = (f"MATCH (n:`{labels[var]}`) WHERE toLower(toString(n.`{prop}`)) CONTAINS '{needle}' "
                 f"RETURN DISTINCT n.`{prop}` AS value LIMIT 5")
            out.append((labels[var], prop, value, q))
    return out
