#!/usr/bin/env python3
"""Deterministic scorer for product-listing → JSON.
score(raw_text, gold) -> dict(valid, fields{name: bool}, n_correct, all_correct, parsed)
Invalid (no parse / schema violation) => every field False.
Run `python3 score.py` to execute the unit tests."""
import json, re, os

SCHEMA = json.load(open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "schema.json")))
FIELDS = SCHEMA["required"]
ENUMS = {k: set(v["enum"]) for k, v in SCHEMA["properties"].items() if "enum" in v}


def extract_json(raw):
    """Guardrail: pull the first JSON object out of whatever the model said (code fences, leaked thinking, prose)."""
    if raw is None:
        return None
    s = raw
    if "</think>" in s:
        s = s.split("</think>")[-1]
    s = s.strip()
    m = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", s, re.S)
    if m:
        s = m.group(1)
    try:
        return json.loads(s)
    except Exception:
        pass
    # first balanced {...}
    start = s.find("{")
    while start != -1:
        depth = 0
        for i in range(start, len(s)):
            if s[i] == "{": depth += 1
            elif s[i] == "}":
                depth -= 1
                if depth == 0:
                    try:
                        return json.loads(s[start:i + 1])
                    except Exception:
                        break
        start = s.find("{", start + 1)
    return None


def validate(obj):
    """Schema check without jsonschema dependency. Returns list of problems (empty = valid)."""
    probs = []
    if not isinstance(obj, dict):
        return ["not an object"]
    for k in FIELDS:
        if k not in obj: probs.append(f"missing {k}")
    for k in obj:
        if k not in FIELDS: probs.append(f"extra key {k}")
    if probs:
        return probs
    if not isinstance(obj["brand"], str): probs.append("brand not string")
    def in_enum(k, v):  # enum check is case/whitespace-insensitive (guardrail); exact match happens in norm()
        return isinstance(v, str) and re.sub(r"\s+", " ", v.strip().lower()) in ENUMS[k]
    if not in_enum("product_type", obj["product_type"]): probs.append("product_type not in enum")
    if obj["color"] is not None and not in_enum("color", obj["color"]): probs.append("color not in enum")
    if obj["size"] is not None and not isinstance(obj["size"], str): probs.append("size not string/null")
    if obj["material"] is not None and not in_enum("material", obj["material"]): probs.append("material not in enum")
    p = obj["price_usd"]
    if p is not None and (isinstance(p, bool) or not isinstance(p, (int, float))): probs.append("price not number/null")
    q = obj["quantity"]
    if isinstance(q, bool) or not isinstance(q, int) or q < 1: probs.append("quantity not int>=1")
    if not isinstance(obj["is_bundle"], bool): probs.append("is_bundle not bool")
    return probs


def norm(field, v):
    if v is None:
        return None
    if field == "price_usd":
        return round(float(v) + 1e-9, 2)
    if field == "quantity":
        return int(v)
    if field == "is_bundle":
        return bool(v)
    s = str(v).strip().lower()
    s = re.sub(r"[®™©]", "", s)
    s = re.sub(r"\s+", " ", s).strip()
    if field == "size":
        s = s.replace(" ", "").replace("-", "").upper()
    return s


def score(raw, gold):
    obj = extract_json(raw)
    probs = validate(obj) if obj is not None else ["no json"]
    if probs:
        return {"valid": False, "problems": probs, "fields": {k: False for k in FIELDS}, "n_correct": 0, "all_correct": False, "parsed": obj}
    fields = {k: norm(k, obj[k]) == norm(k, gold[k]) for k in FIELDS}
    n = sum(fields.values())
    return {"valid": True, "problems": [], "fields": fields, "n_correct": n, "all_correct": n == len(FIELDS), "parsed": obj}


def _tests():
    gold = {"brand": "Amazon Basics", "product_type": "water bottle", "color": "blue", "size": "32oz", "material": "stainless steel", "price_usd": 24.99, "quantity": 2, "is_bundle": False}
    # 1. exact
    r = score(json.dumps(gold), gold); assert r["valid"] and r["all_correct"], r
    # 2. normalisation: case, ®, whitespace, size spacing, price as string-ish int formatting
    r = score('```json\n{"brand":"AMAZON BASICS®","product_type":"water bottle","color":"Blue","size":"32 oz","material":"Stainless Steel","price_usd":24.990,"quantity":2,"is_bundle":false}\n```', gold)
    assert r["valid"] and r["all_correct"], r
    # 3. wrong answer scores 0 on the wrong fields, not all
    wrong = dict(gold, price_usd=39.99, color="red"); r = score(json.dumps(wrong), gold)
    assert r["valid"] and not r["all_correct"] and r["n_correct"] == 6 and not r["fields"]["price_usd"] and not r["fields"]["color"], r
    # 4. invalid: enum violation -> invalid, all fields 0
    r = score(json.dumps(dict(gold, color="teal")), gold); assert not r["valid"] and r["n_correct"] == 0, r
    # 5. invalid: prose, no JSON
    r = score("The brand is Amazon Basics and it costs $24.99", gold); assert not r["valid"] and r["n_correct"] == 0, r
    # 6. leaked thinking then JSON is recovered
    r = score("<think>hmm</think>Here you go: " + json.dumps(gold) + " hope that helps", gold); assert r["valid"] and r["all_correct"], r
    # 7. extra key -> invalid; quantity as float -> invalid
    assert not score(json.dumps(dict(gold, extra=1)), gold)["valid"]
    assert not score(json.dumps(dict(gold, quantity=2.0)), gold)["valid"]
    print("score.py: all 7 unit tests passed")


if __name__ == "__main__":
    _tests()
