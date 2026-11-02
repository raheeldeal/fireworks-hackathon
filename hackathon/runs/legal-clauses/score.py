#!/usr/bin/env python3
"""Deterministic scorer for legal clause classification. `python3 score.py --test` runs the unit tests."""
import json, os, re, sys

HERE = os.path.dirname(os.path.abspath(__file__))
LABELS = [l["name"] for l in json.load(open(os.path.join(HERE, "data", "labels.json")))["labels"]]
_BY_KEY = {}

def _key(s):
    return re.sub(r"[^a-z0-9]+", " ", s.lower()).strip()

for _l in LABELS:
    _BY_KEY[_key(_l)] = _l

def normalize(answer):
    """Map a raw model output to one of the 100 labels, or 'invalid'. Tolerates thinking leakage, quotes,
    'Category:' prefixes, JSON {"label": ...}, markdown and trailing punctuation. Never guesses between labels."""
    if not answer:
        return "invalid"
    a = answer
    if "</think>" in a:
        a = a.split("</think>")[-1]
    a = a.strip()
    # JSON object output
    if a.startswith("{"):
        try:
            obj = json.loads(a)
            for k in ("label", "category", "answer", "class"):
                if isinstance(obj.get(k), str):
                    a = obj[k]
                    break
        except Exception:
            m = re.search(r'"(?:label|category|answer|class)"\s*:\s*"([^"]+)"', a)
            if m:
                a = m.group(1)
    a = a.strip().strip("`*_\"'.:; \n")
    a = re.sub(r"^(category|label|answer|classification)\s*[:=-]\s*", "", a, flags=re.I).strip("`*_\"'. ")
    cand = a.splitlines()[0].strip() if a else ""
    k = _key(cand)
    if k in _BY_KEY:
        return _BY_KEY[k]
    # whole answer is exactly one label somewhere on its own line
    lines = [_key(x) for x in a.splitlines()]
    hits = {_BY_KEY[x] for x in lines if x in _BY_KEY}
    if len(hits) == 1:
        return hits.pop()
    return "invalid"

def metrics(rows):
    """rows: list of {label, pred}. Returns accuracy, macro-F1 over the labels present in gold, invalid count."""
    n = len(rows)
    acc = sum(r["pred"] == r["label"] for r in rows) / n if n else 0.0
    gold_labels = sorted({r["label"] for r in rows})
    f1s = []
    for lab in gold_labels:
        tp = sum(r["pred"] == lab and r["label"] == lab for r in rows)
        fp = sum(r["pred"] == lab and r["label"] != lab for r in rows)
        fn = sum(r["pred"] != lab and r["label"] == lab for r in rows)
        p = tp / (tp + fp) if tp + fp else 0.0
        rc = tp / (tp + fn) if tp + fn else 0.0
        f1s.append(2 * p * rc / (p + rc) if p + rc else 0.0)
    return {"accuracy": round(acc, 4), "macro_f1": round(sum(f1s) / len(f1s), 4) if f1s else 0.0,
            "invalid": sum(r["pred"] == "invalid" for r in rows), "n": n}

def _test():
    cases = [
        ("Governing Laws", "Governing Laws"),
        ("  governing laws.\n", "Governing Laws"),
        ('{"label": "Waiver Of Jury Trials"}', "Waiver Of Jury Trials"),
        ("<think>hmm, this is about notices</think>\nCategory: **Notices**", "Notices"),
        ("Governing Law", "invalid"),            # not in the label set (singular): must be invalid, not a guess
        ("Severability or Waivers", "invalid"),  # two labels, ambiguous
        ("", "invalid"),
    ]
    for raw, want in cases:
        got = normalize(raw)
        assert got == want, (raw, got, want)
    m = metrics([{"label": "Notices", "pred": "Notices"}, {"label": "Taxes", "pred": "Fees"}, {"label": "Taxes", "pred": "invalid"}])
    assert m["accuracy"] == round(1 / 3, 4) and m["invalid"] == 1
    assert abs(m["macro_f1"] - 0.5) < 1e-9, m   # Notices f1=1, Taxes f1=0
    print("score.py: all tests passed")

if __name__ == "__main__":
    if "--test" in sys.argv:
        _test()
    else:
        print(normalize(sys.stdin.read()))
