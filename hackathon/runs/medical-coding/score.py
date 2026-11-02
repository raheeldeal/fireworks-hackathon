"""Deterministic scorer for clinical note -> ICD-10-CM category codes.
score(raw_output, gold_codes) -> dict(pred=set, f1=float, exact=bool, invalid=bool)
Run `python3 score.py` to execute the unit tests."""
import json, os, re

HERE = os.path.dirname(os.path.abspath(__file__))
VALID = {c for c, _ in json.load(open(os.path.join(HERE, "data", "codes.json")))["codes"]}
CODE_RE = re.compile(r"\b([A-Z]\d{2})(?:\.\d{1,4})?\b")


def normalize(raw):
    """Turn whatever the model said into a set of in-list category codes.
    Accepts a JSON array, a JSON object with a 'codes' key, or loose text with codes in it.
    Sub-category codes (E11.9) are truncated to the category (E11). Codes outside the
    60-code list are dropped. Returns (codes, invalid_flag)."""
    if not raw:
        return set(), True
    txt = raw
    if "</think>" in txt:
        txt = txt.split("</think>")[-1]
    found = []
    # Prefer a JSON structure if present
    m = re.search(r"\[[^\[\]]*\]", txt, re.S)
    obj = None
    try:
        obj = json.loads(txt.strip().strip("`").replace("json\n", "", 1))
    except Exception:
        if m:
            try:
                obj = json.loads(m.group(0))
            except Exception:
                obj = None
    if isinstance(obj, dict):
        obj = obj.get("codes") or obj.get("icd10") or obj.get("icd10_codes") or []
    if isinstance(obj, list):
        for item in obj:
            s = item if isinstance(item, str) else (item.get("code") if isinstance(item, dict) else "")
            mm = CODE_RE.search(str(s).upper().strip())
            if mm:
                found.append(mm.group(1))
    if not found:  # fall back to scanning the text (after any JSON attempt)
        found = [mm.group(1) for mm in CODE_RE.finditer(txt.upper())]
    codes = {c for c in found if c in VALID}
    return codes, len(codes) == 0


def score(raw, gold):
    gold = set(gold)
    pred, invalid = normalize(raw)
    tp = len(pred & gold)
    if tp == 0:
        f1 = 0.0
    else:
        p = tp / len(pred)
        r = tp / len(gold)
        f1 = 2 * p * r / (p + r)
    return {"pred": sorted(pred), "f1": round(f1, 4), "exact": pred == gold, "invalid": invalid}


def _tests():
    cases = [
        ('["E11","I10"]', ["E11", "I10"], 1.0, True, False),            # exact
        ('{"codes": ["E11.9", "I10", "Z99"]}', ["E11", "I10"], 1.0, True, False),  # subcode truncated, Z99 dropped (not in list)
        ('The codes are E11 and J44.', ["E11", "I10"], 0.5, False, False),  # loose text, half right
        ('["K21"]', ["E11", "I10"], 0.0, False, False),                 # wrong answer must score 0
        ('I cannot determine the codes.', ["E11"], 0.0, False, True),   # unparseable -> invalid, scores 0
        ('', ["E11"], 0.0, False, True),                                 # empty (reasoning model ran out) -> invalid
        ('["E11","E11","I10","I10"]', ["E11", "I10"], 1.0, True, False),  # duplicates collapse
    ]
    for raw, gold, f1, exact, invalid in cases:
        s = score(raw, gold)
        assert abs(s["f1"] - f1) < 1e-6, (raw, s)
        assert s["exact"] == exact, (raw, s)
        assert s["invalid"] == invalid, (raw, s)
    print(f"score.py: {len(cases)} unit tests passed")


if __name__ == "__main__":
    _tests()
