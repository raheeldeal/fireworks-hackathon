#!/usr/bin/env python3
"""Build data/test.jsonl (HumanEvalFix, 164 rows) and data/train.jsonl (MBPP + AST-injected bugs).

Usage: python3 build_data.py --raw <dir with rows.jsonl and sanitized-mbpp.json> [--test-only]
The user-facing text of each row = buggy function + failing test output, produced by actually running
the buggy code against the tests in the sandbox (so the error message is real, not written by a model).
"""
import argparse, ast, copy, json, os, random, sys
from sandbox import run_program

HERE = os.path.dirname(os.path.abspath(__file__))

USER_TEMPLATE = """The following Python function has a bug. A unit test fails with the output shown.

```python
{code}
```

Failing test output:
```
{error}
```"""


def hef_buggy_code(r):
    return (r["declaration"].rstrip("\n") + "\n" + r["buggy_solution"]).rstrip() + "\n"


def hef_fixed_code(r):
    return (r["declaration"].rstrip("\n") + "\n" + r["canonical_solution"]).rstrip() + "\n"


def hef_test_program(r, code):
    return r["import"] + "\n" + code + "\n" + r["test_setup"] + "\n" + r["test"] + "\n"


def build_test(raw):
    rows = [json.loads(l) for l in open(os.path.join(raw, "rows.jsonl"))]
    rows.sort(key=lambda r: int(r["task_id"].split("/")[1]))
    out = []
    for r in rows:
        buggy = hef_buggy_code(r)
        status, err = run_program(hef_test_program(r, buggy))
        assert status in ("fail", "timeout"), (r["task_id"], status, err)
        fixed_status, ferr = run_program(hef_test_program(r, hef_fixed_code(r)))
        assert fixed_status == "pass", (r["task_id"], fixed_status, ferr)
        out.append({
            "id": r["task_id"].replace("/", "-"),
            "source": "bigcode/humanevalpack python (HumanEvalFix)",
            "entry_point": r["entry_point"],
            "bug_type": r["bug_type"],
            "buggy_code": buggy,
            "error": err,
            "text": USER_TEMPLATE.format(code=buggy.rstrip(), error=err),
            "reference": hef_fixed_code(r),
            "test_program_prefix": r["import"] + "\n",
            "test_program_suffix": "\n" + r["test_setup"] + "\n" + r["test"] + "\n",
        })
    return out


# ---------- MBPP bug injection (rule-based, no model involved) ----------
CMP_SWAP = {ast.Lt: ast.LtE, ast.LtE: ast.Lt, ast.Gt: ast.GtE, ast.GtE: ast.Gt, ast.Eq: ast.NotEq, ast.NotEq: ast.Eq}
ARITH_SWAP = {ast.Add: ast.Sub, ast.Sub: ast.Add, ast.Mult: ast.FloorDiv, ast.FloorDiv: ast.Mult, ast.Mod: ast.FloorDiv}


def mutants(tree):
    """Yield (name, mutated_tree) for every single-site mutation we know how to make."""
    nodes = list(ast.walk(tree))
    for i, n in enumerate(nodes):
        if isinstance(n, ast.Compare) and len(n.ops) == 1 and type(n.ops[0]) in CMP_SWAP:
            t = copy.deepcopy(tree); m = list(ast.walk(t))[i]; m.ops[0] = CMP_SWAP[type(n.ops[0])]()
            yield "wrong_comparison", t
        if isinstance(n, ast.BinOp) and type(n.op) in ARITH_SWAP:
            t = copy.deepcopy(tree); m = list(ast.walk(t))[i]; m.op = ARITH_SWAP[type(n.op)]()
            yield "wrong_operator", t
        if isinstance(n, ast.Constant) and isinstance(n.value, int) and not isinstance(n.value, bool) and abs(n.value) < 1000:
            for d in (1, -1):
                t = copy.deepcopy(tree); m = list(ast.walk(t))[i]; m.value = n.value + d
                yield "off_by_one", t
        if isinstance(n, ast.Constant) and isinstance(n.value, bool):
            t = copy.deepcopy(tree); m = list(ast.walk(t))[i]; m.value = not n.value
            yield "wrong_return", t
        if isinstance(n, ast.BoolOp):
            t = copy.deepcopy(tree); m = list(ast.walk(t))[i]; m.op = ast.Or() if isinstance(n.op, ast.And) else ast.And()
            yield "wrong_boolean", t
        if isinstance(n, ast.Return) and isinstance(n.value, ast.Name):
            t = copy.deepcopy(tree); m = list(ast.walk(t))[i]
            names = sorted({x.id for x in ast.walk(t) if isinstance(x, ast.Name) and x.id != n.value.id and x.id not in ("len", "range", "print")})
            if names:
                m.value = ast.Name(id=names[0], ctx=ast.Load()); yield "wrong_return", t
        if isinstance(n, (ast.If, ast.For, ast.While)) and len(n.body) > 1:
            t = copy.deepcopy(tree); m = list(ast.walk(t))[i]; m.body = m.body[:-1]
            yield "missing_logic", t


def build_train(raw, test_rows, n_target, seed=13):
    rng = random.Random(seed)
    data = json.load(open(os.path.join(raw, "sanitized-mbpp.json")))
    test_names = {r["entry_point"] for r in test_rows}
    out = []
    for p in data:
        code = p["code"]
        try:
            tree = ast.parse(code)
        except SyntaxError:
            continue
        funcs = [n for n in tree.body if isinstance(n, ast.FunctionDef)]
        if not funcs:
            continue
        entry = funcs[-1].name
        if entry in test_names:
            continue
        tests = "\n".join(p["test_imports"]) + "\n" + "\n".join(p["test_list"]) + "\n"
        if run_program(code + "\n" + tests)[0] != "pass":
            continue
        cands = list(mutants(tree))
        rng.shuffle(cands)
        for kind, t in cands[:6]:
            try:
                buggy = ast.unparse(ast.fix_missing_locations(t)) + "\n"
            except Exception:
                continue
            if buggy.strip() == ast.unparse(tree).strip():
                continue
            status, err = run_program(buggy + "\n" + tests)
            if status not in ("fail", "timeout"):
                continue
            out.append({
                "id": f"mbpp-{p['task_id']}",
                "source": "google-research mbpp sanitized + rule-based AST mutation",
                "entry_point": entry,
                "bug_type": kind,
                "buggy_code": buggy,
                "error": err,
                "text": USER_TEMPLATE.format(code=buggy.rstrip(), error=err),
                "reference": ast.unparse(tree) + "\n",
                "test_program_prefix": "\n".join(p["test_imports"]) + "\n",
                "test_program_suffix": "\n" + "\n".join(p["test_list"]) + "\n",
            })
            break
        if len(out) >= n_target:
            break
        if len(out) % 50 == 0 and out:
            print("train so far", len(out), file=sys.stderr)
    return out


def dump(rows, path):
    with open(path, "w") as f:
        for r in rows:
            f.write(json.dumps(r) + "\n")
    print(f"wrote {len(rows)} rows -> {path}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--raw", required=True)
    ap.add_argument("--test-only", action="store_true")
    ap.add_argument("--n-train", type=int, default=300)
    a = ap.parse_args()
    os.makedirs(os.path.join(HERE, "data"), exist_ok=True)
    test_path = os.path.join(HERE, "data", "test.jsonl")
    if os.path.exists(test_path):
        print("test.jsonl exists; NOT overwriting (locked)")
        test_rows = [json.loads(l) for l in open(test_path)]
    else:
        test_rows = build_test(a.raw)
        dump(test_rows, test_path)
    if not a.test_only:
        dump(build_train(a.raw, test_rows, a.n_train), os.path.join(HERE, "data", "train.jsonl"))
