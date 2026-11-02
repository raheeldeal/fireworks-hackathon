#!/usr/bin/env python3
"""Build data/test.jsonl (locked) and data/train.jsonl from the BFCL v4 raw files in raw/.

Row format (both files):
  id, source (bfcl file), messages (list of {role, content} — the conversation so far),
  tools (OpenAI function schemas, converted from BFCL's python-ish types),
  answer: {"name": <function>, "arguments": {<arg>: <canonical value>}}   (one canonical gold call)
  acceptable: {<function>: {<arg>: [acceptable values...]}}             (BFCL possible_answer; "" = may be omitted)
"""
import json, random, os, sys

RAW = "raw"
FILES = {
    "simple_python": ("BFCL_v4_simple_python.json", 40, 80),
    "multiple":      ("BFCL_v4_multiple.json",      50, 100),
    "live_simple":   ("BFCL_v4_live_simple.json",   40, 80),
    "live_multiple": ("BFCL_v4_live_multiple.json", 70, 140),
}
MAX_CHARS = 8000   # drop monsters (37-tool catalogs) that would dominate token cost
SEED = 20261101

TYPE_MAP = {"dict": "object", "float": "number", "tuple": "array", "integer": "integer", "string": "string",
            "boolean": "boolean", "array": "array", "number": "number", "object": "object"}

def convert_schema(s):
    """BFCL uses python-ish types (dict/float/tuple/any). Make it valid JSON Schema."""
    if not isinstance(s, dict):
        return s
    out = {}
    for k, v in s.items():
        if k == "type":
            if v == "any":
                continue
            out[k] = TYPE_MAP.get(v, v)
        elif k == "properties" and isinstance(v, dict):
            out[k] = {pk: convert_schema(pv) for pk, pv in v.items()}
        elif k == "items":
            out[k] = convert_schema(v)
        else:
            out[k] = v
    return out

def load(name):
    rows = [json.loads(l) for l in open(os.path.join(RAW, name)) if l.strip()]
    ans = {}
    for l in open(os.path.join(RAW, "ans_" + name)):
        if l.strip():
            a = json.loads(l); ans[a["id"]] = a["ground_truth"]
    return rows, ans

def canonical(acceptable):
    """One gold call from BFCL's acceptable-value lists: first non-empty value per arg; omit args that allow ''."""
    (fname, args), = acceptable.items()
    out = {}
    for k, vals in args.items():
        if "" in vals:
            continue            # optional arg: canonical answer omits it
        out[k] = vals[0]
    return {"name": fname, "arguments": out}

def main():
    rng = random.Random(SEED)
    test, train = [], []
    for src, (fname, n_test, n_train) in FILES.items():
        rows, ans = load(fname)
        pool = []
        for r in rows:
            gt = ans[r["id"]]
            if len(gt) != 1:
                continue
            msgs = r["question"][0]
            if any(m["role"] not in ("user", "system") for m in msgs):
                continue
            tools = [{"type": "function", "function": {"name": f["name"], "description": f.get("description", ""),
                      "parameters": convert_schema(f["parameters"])}} for f in r["function"]]
            size = len(json.dumps(tools)) + len(json.dumps(msgs))
            if size > MAX_CHARS:
                continue
            (fn, gargs), = gt[0].items()
            if fn not in {f["name"] for f in r["function"]}:
                continue
            if any(not isinstance(v, list) or len(v) == 0 for v in gargs.values()):
                continue        # 3 live_simple rows have empty acceptable lists (ambiguous label): drop
            pool.append({"id": r["id"], "source": fname, "messages": msgs, "tools": tools,
                         "answer": canonical(gt[0]), "acceptable": gt[0]})
        rng.shuffle(pool)
        test += pool[:n_test]
        train += pool[n_test:n_test + n_train]
        print(f"{src}: {len(rows)} raw, {len(pool)} usable, {n_test} test, {min(n_train, len(pool)-n_test)} train")
    rng.shuffle(test); rng.shuffle(train)
    os.makedirs("data", exist_ok=True)
    if os.path.exists("data/test.jsonl") and "--force" not in sys.argv:
        sys.exit("data/test.jsonl exists and is LOCKED; refusing to overwrite (pass --force only before the lock).")
    with open("data/test.jsonl", "w") as f:
        for r in test: f.write(json.dumps(r) + "\n")
    with open("data/train.jsonl", "w") as f:
        for r in train: f.write(json.dumps(r) + "\n")
    print(f"wrote {len(test)} test rows, {len(train)} train rows")

if __name__ == "__main__":
    main()
