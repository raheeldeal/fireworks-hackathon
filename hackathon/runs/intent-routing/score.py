#!/usr/bin/env python3
"""Deterministic scorer for Banking77 intent routing.
parse(raw) -> (pred_label | "invalid", confidence | None)
score(raw, gold) -> 1 or 0
Run `python3 score.py` to execute the unit tests."""
import json, os, re

LABELS = list(json.load(open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "labels.json"))))

def canon(s):
    return str(s).strip().strip("\"'`.").lower().rstrip("?").replace(" ", "_").replace("-", "_")

CANON2LABEL = {canon(l): l for l in LABELS}

def _strip_think(s):
    if "</think>" in s:
        s = s.split("</think>")[-1]
    return s

def _extract_json(s):
    # first balanced {...} block
    m = re.search(r"\{.*?\}", s, re.S)
    if not m:
        return None
    try:
        return json.loads(m.group(0))
    except json.JSONDecodeError:
        return None

def parse(raw):
    """Return (label or 'invalid', confidence or None). Tolerates code fences, JSON, bare labels, trailing text."""
    if not raw:
        return "invalid", None
    s = _strip_think(raw).strip()
    s = re.sub(r"^```(?:json)?\s*|\s*```$", "", s, flags=re.I).strip()
    conf = None
    obj = _extract_json(s)
    if isinstance(obj, dict):
        cand = obj.get("intent") or obj.get("label") or obj.get("category")
        c = obj.get("confidence")
        if isinstance(c, (int, float)):
            conf = max(0.0, min(1.0, float(c)))
        elif isinstance(c, str):
            try:
                conf = max(0.0, min(1.0, float(c.strip().rstrip("%")) / (100 if "%" in c else 1)))
            except ValueError:
                conf = None
        if cand is not None:
            lab = CANON2LABEL.get(canon(cand))
            return (lab if lab else "invalid"), conf
    # bare label: whole string, or first line
    for piece in (s, s.splitlines()[0] if s.splitlines() else s):
        lab = CANON2LABEL.get(canon(piece))
        if lab:
            return lab, conf
    # label embedded in prose: pick the longest label string present as a whole token
    low = s.lower()
    hits = [l for c, l in CANON2LABEL.items()
            if re.search(r"(?<![a-z])" + re.escape(c).replace("_", "[ _\\-]") + r"(?![a-z_])", low)]
    if hits:
        return max(hits, key=len), conf
    return "invalid", conf

def score(raw, gold):
    pred, _ = parse(raw)
    return 1 if pred != "invalid" and canon(pred) == canon(gold) else 0

TESTS = [
    ("card_arrival", "card_arrival", 1),                                          # bare label
    ('{"intent": "card_arrival", "confidence": 0.91}', "card_arrival", 1),        # JSON
    ("```json\n{\"intent\":\"Refund_not_showing_up\",\"confidence\":0.6}\n```", "Refund_not_showing_up", 1),  # fenced, odd case
    ('{"intent": "pending_transfer", "confidence": 0.8}', "transfer_timing", 0),  # wrong answer must be 0
    ("I think this is about something else entirely", "card_arrival", 0),         # invalid must be 0
    ("The intent is: reverted_card_payment?", "reverted_card_payment?", 1),       # embedded label with ?
    ("<think>hmm</think>\nchange_pin", "change_pin", 1),                           # leaked thinking
    ("", "change_pin", 0),                                                        # empty (reasoning cut off)
]

if __name__ == "__main__":
    ok = 0
    for raw, gold, want in TESTS:
        got = score(raw, gold)
        pred, conf = parse(raw)
        print(("PASS" if got == want else "FAIL"), repr(raw[:40]), "->", pred, conf, "want", want)
        ok += got == want
    print(f"{ok}/{len(TESTS)} passed")
    raise SystemExit(0 if ok == len(TESTS) else 1)
