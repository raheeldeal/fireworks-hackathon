"""Serialize a Spider database schema (from tables.json) into compact DDL-like text."""
import json, os

def load_tables(path):
    return {t["db_id"]: t for t in json.load(open(path))}

def schema_text(t):
    cols_by_table = {}
    for i, (ti, cname) in enumerate(t["column_names_original"]):
        if ti < 0:
            continue
        cols_by_table.setdefault(ti, []).append((i, cname, t["column_types"][i]))
    pks = set(t["primary_keys"])
    fks = {}
    for a, b in t["foreign_keys"]:
        fks[a] = b
    lines = []
    col_full = lambda ci: f'{t["table_names_original"][t["column_names_original"][ci][0]]}.{t["column_names_original"][ci][1]}'
    for ti, tname in enumerate(t["table_names_original"]):
        parts = []
        for ci, cname, ctype in cols_by_table.get(ti, []):
            s = f"{cname} {ctype}"
            if ci in pks:
                s += " PK"
            if ci in fks:
                s += f" FK->{col_full(fks[ci])}"
            parts.append(s)
        lines.append(f"{tname}({', '.join(parts)})")
    return "\n".join(lines)

def approx_tokens(s):
    return int(len(s) / 3.3) + 1
