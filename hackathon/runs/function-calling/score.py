#!/usr/bin/env python3
"""Deterministic scorer for function-calling predictions against BFCL-style acceptable answers.

score(pred, acceptable) -> dict(strict, partial, invalid, name_ok, args_ok, reason)
  pred:        {"name": str, "arguments": dict} or None (unparseable output)
  acceptable:  {fn_name: {arg: [acceptable values, "" means the arg may be omitted]}}

Rules (see SPEC.md):
  * function name: case-insensitive, '.' and '_' treated the same (tool-API names cannot contain dots)
  * argument keys lowercased; every provided key must exist in the gold spec (extra keys = wrong)
  * required args (no "" in acceptable list) must be present; optional ones may be omitted
  * a provided value must equal one acceptable value after normalization:
      numbers: numeric equality (5 == 5.0; "5" parses to 5);  bools: True == "true"
      strings: whitespace-stripped, case-insensitive;  lists: same length, element-wise, ordered
      dicts: keys lowercased, recursive
  * strict = 1 if name and all args correct; partial = 1 if strict, 0.5 if only the name is right, else 0
  * invalid (no parseable call) scores 0 on both and is counted separately
"""
import json, re

def norm_name(n):
    return str(n).strip().lower().replace(".", "_")

def _num(v):
    if isinstance(v, bool):
        return None
    if isinstance(v, (int, float)):
        return float(v)
    if isinstance(v, str):
        try:
            return float(v.strip())
        except ValueError:
            return None
    return None

def values_equal(pred, acc):
    if isinstance(acc, bool):
        if isinstance(pred, bool):
            return pred == acc
        return isinstance(pred, str) and pred.strip().lower() == str(acc).lower()
    if isinstance(acc, (int, float)):
        p = _num(pred)
        return p is not None and abs(p - float(acc)) < 1e-6
    if isinstance(acc, str):
        if isinstance(pred, (list, dict, bool)) or pred is None:
            return False
        a = acc.strip().lower()
        p = str(pred).strip().lower()
        if p == a:
            return True
        # numeric-looking strings: "5" vs "5.0"
        pa, pb = _num(acc), _num(pred)
        return pa is not None and pb is not None and abs(pa - pb) < 1e-6
    if isinstance(acc, list):
        if isinstance(pred, str):          # model may stringify lists
            try:
                pred = json.loads(pred)
            except Exception:
                return False
        if not isinstance(pred, list) or len(pred) != len(acc):
            return False
        return all(values_equal(p, a) for p, a in zip(pred, acc))
    if isinstance(acc, dict):
        if isinstance(pred, str):
            try:
                pred = json.loads(pred)
            except Exception:
                return False
        if not isinstance(pred, dict):
            return False
        pk = {str(k).lower(): v for k, v in pred.items()}
        ak = {str(k).lower(): v for k, v in acc.items()}
        return pk.keys() == ak.keys() and all(values_equal(pk[k], ak[k]) for k in ak)
    return pred == acc

def score(pred, acceptable):
    (gold_name, gold_args), = acceptable.items()
    if not pred or not isinstance(pred, dict) or "name" not in pred:
        return {"strict": 0.0, "partial": 0.0, "invalid": True, "name_ok": False, "args_ok": False, "reason": "invalid: no parseable call"}
    name_ok = norm_name(pred["name"]) == norm_name(gold_name)
    args = pred.get("arguments")
    if isinstance(args, str):
        try:
            args = json.loads(args)
        except Exception:
            args = None
    if not isinstance(args, dict):
        args = {} if args is None else None
    if args is None:
        return {"strict": 0.0, "partial": 0.5 if name_ok else 0.0, "invalid": False, "name_ok": name_ok, "args_ok": False, "reason": "arguments not a JSON object"}
    pargs = {str(k).strip().lower(): v for k, v in args.items()}
    gargs = {str(k).strip().lower(): v for k, v in gold_args.items()}
    reasons = []
    for k in pargs:
        if k not in gargs:
            reasons.append(f"extra arg '{k}'")
    for k, acc_vals in gargs.items():
        optional = "" in acc_vals
        if k not in pargs:
            if not optional:
                reasons.append(f"missing arg '{k}'")
            continue
        candidates = [a for a in acc_vals if a != ""]
        if not any(values_equal(pargs[k], a) for a in candidates):
            reasons.append(f"arg '{k}': got {json.dumps(pargs[k])[:60]}, want one of {json.dumps(candidates)[:80]}")
    args_ok = not reasons
    if not name_ok:
        reasons.insert(0, f"name: got {pred['name']}, want {gold_name}")
    strict = 1.0 if (name_ok and args_ok) else 0.0
    partial = 1.0 if strict else (0.5 if name_ok else 0.0)
    return {"strict": strict, "partial": partial, "invalid": False, "name_ok": name_ok, "args_ok": args_ok, "reason": "; ".join(reasons) or "ok"}

# ---------- guardrail: turn messy model text into a call dict (or None) ----------
_FENCE = re.compile(r"```(?:json|python|javascript)?\s*(.*?)```", re.S)

def _balanced_json_objects(text):
    """Yield candidate JSON substrings starting at each '{' or '[' with balanced brackets."""
    for i, ch in enumerate(text):
        if ch not in "{[":
            continue
        depth, in_str, esc = 0, False, False
        for j in range(i, len(text)):
            c = text[j]
            if in_str:
                if esc: esc = False
                elif c == "\\": esc = True
                elif c == '"': in_str = False
            elif c == '"': in_str = True
            elif c in "{[": depth += 1
            elif c in "}]":
                depth -= 1
                if depth == 0:
                    yield text[i:j + 1]
                    break

def _as_call(obj):
    if isinstance(obj, list) and obj:
        obj = obj[0]
    if not isinstance(obj, dict):
        return None
    if "function" in obj and isinstance(obj["function"], dict):
        obj = obj["function"]
    if "name" in obj:
        args = obj.get("arguments", obj.get("parameters", obj.get("args", {})))
        return {"name": obj["name"], "arguments": args}
    if len(obj) == 1:                       # {"fn_name": {args}}
        (k, v), = obj.items()
        if isinstance(v, dict):
            return {"name": k, "arguments": v}
    return None

def parse_call(text):
    """Extract one function call from free text. Returns {"name","arguments"} or None."""
    if not text:
        return None
    if "</think>" in text:
        text = text.split("</think>")[-1]
    cands = [m.group(1) for m in _FENCE.finditer(text)] + [text]
    for c in cands:
        for sub in _balanced_json_objects(c):
            try:
                call = _as_call(json.loads(sub))
            except Exception:
                continue
            if call:
                return call
    return None

# ---------- unit tests ----------
def _tests():
    acc = {"calculate_triangle_area": {"base": [10], "height": [5], "unit": ["units", ""]}}
    # 1. exact, optional omitted
    assert score({"name": "calculate_triangle_area", "arguments": {"base": 10, "height": 5}}, acc)["strict"] == 1
    # 2. numeric equality + optional provided with acceptable value + key case
    assert score({"name": "calculate_triangle_area", "arguments": {"Base": 10.0, "height": "5", "unit": " Units "}}, acc)["strict"] == 1
    # 3. wrong argument value: name right -> partial 0.5, strict 0
    r = score({"name": "calculate_triangle_area", "arguments": {"base": 10, "height": 6}}, acc)
    assert r["strict"] == 0 and r["partial"] == 0.5 and "height" in r["reason"]
    # 4. wrong function name -> 0 on both
    r = score({"name": "calculate_circle_area", "arguments": {"base": 10, "height": 5}}, acc)
    assert r["strict"] == 0 and r["partial"] == 0
    # 5. invalid output -> 0, flagged
    r = score(parse_call("I cannot help with that."), acc)
    assert r["invalid"] and r["strict"] == 0 and r["partial"] == 0
    # 6. missing required arg / extra arg
    assert score({"name": "calculate_triangle_area", "arguments": {"base": 10}}, acc)["strict"] == 0
    assert score({"name": "calculate_triangle_area", "arguments": {"base": 10, "height": 5, "color": "red"}}, acc)["strict"] == 0
    # 7. parsing guardrail: fenced, dotted name, stringified arguments, list wrapper
    p = parse_call('Sure:\n```json\n{"name": "math.factorial", "arguments": "{\\"number\\": 5}"}\n```')
    assert score(p, {"math.factorial": {"number": [5]}})["strict"] == 1
    p = parse_call('[{"function": {"name": "math_factorial", "arguments": {"number": 5}}}]')
    assert score(p, {"math.factorial": {"number": [5]}})["strict"] == 1
    # 8. list and dict args
    acc2 = {"f": {"pts": [[[3, 4]]], "opts": [{"a": 1}], "flag": [True, ""]}}
    assert score({"name": "f", "arguments": {"pts": [[3, 4]], "opts": {"A": 1.0}, "flag": "true"}}, acc2)["strict"] == 1
    assert score({"name": "f", "arguments": {"pts": [[4, 3]], "opts": {"a": 1}}}, acc2)["strict"] == 0
    print("score.py: all unit tests passed")

if __name__ == "__main__":
    _tests()
