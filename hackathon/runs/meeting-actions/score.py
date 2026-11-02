#!/usr/bin/env python3
"""Deterministic scorer for meeting-actions. stdlib only.

score_rows(gold_items, raw_output) -> dict(valid, tp, n_pred, n_gold, due_correct, due_total, matches)
Run `python3 score.py` to execute the unit tests.
"""
import json, re
from difflib import SequenceMatcher

TOKEN_SIM = 0.6
STOP = {"the", "a", "an", "to", "for", "of", "on", "in", "and", "with", "up", "out"}


def parse_output(raw):
    """Return a list of dicts, or None if the output is not a JSON array of objects."""
    if raw is None:
        return None
    s = raw.strip()
    if "</think>" in s:
        s = s.split("</think>")[-1].strip()
    s = re.sub(r"^```(?:json)?\s*|\s*```$", "", s, flags=re.S).strip()
    try:
        obj = json.loads(s)
    except json.JSONDecodeError:
        m = re.search(r"\[.*\]", s, flags=re.S)
        if not m:
            return None
        try:
            obj = json.loads(m.group(0))
        except json.JSONDecodeError:
            return None
    if isinstance(obj, dict):  # tolerate {"action_items": [...]}
        lists = [v for v in obj.values() if isinstance(v, list)]
        if len(lists) == 1:
            obj = lists[0]
        else:
            return None
    if not isinstance(obj, list) or not all(isinstance(x, dict) for x in obj):
        return None
    return obj


def norm_tokens(s):
    toks = re.findall(r"[a-z0-9#]+", (s or "").lower())
    return sorted(set(t for t in toks if t not in STOP))


def token_set_ratio(a, b):
    """fuzzywuzzy-style token_set_ratio in [0,1]."""
    ta, tb = set(norm_tokens(a)), set(norm_tokens(b))
    inter = " ".join(sorted(ta & tb))
    t1 = (inter + " " + " ".join(sorted(ta - tb))).strip()
    t2 = (inter + " " + " ".join(sorted(tb - ta))).strip()
    if not t1 and not t2:
        return 1.0
    r = lambda x, y: SequenceMatcher(None, x, y).ratio()
    cands = [r(t1, t2)]
    if inter:
        cands += [r(inter, t1), r(inter, t2)]
    return max(cands)


def norm_owner(s):
    return re.sub(r"[^a-z]", "", str(s or "").lower().split()[0] if str(s or "").strip() else "")


def norm_due(s):
    if s is None:
        return None
    s = str(s).strip().lower()
    if s in ("", "null", "none", "n/a", "tbd", "no deadline"):
        return None
    s = re.sub(r"[^a-z0-9' ]", " ", s)
    s = re.sub(r"^(by|on|before|until|due|at|for)\s+", "", s.strip())
    s = re.sub(r"\b(the|of)\b", " ", s)  # "the end of the quarter" == "end of quarter"
    return re.sub(r"\s+", " ", s).strip()


def score_rows(gold, raw):
    pred = parse_output(raw)
    out = {"valid": pred is not None, "n_gold": len(gold), "n_pred": 0, "tp": 0, "due_correct": 0, "due_total": 0,
           "matches": [], "unmatched_pred": [], "unmatched_gold": []}
    if pred is None:
        out["unmatched_gold"] = list(range(len(gold)))
        return out
    out["n_pred"] = len(pred)
    cands = []
    for i, g in enumerate(gold):
        for j, p in enumerate(pred):
            if norm_owner(p.get("owner")) == norm_owner(g["owner"]):
                sim = token_set_ratio(p.get("task", ""), g["task"])
                if sim >= TOKEN_SIM:
                    cands.append((sim, i, j))
    used_g, used_p = set(), set()
    for sim, i, j in sorted(cands, key=lambda x: (-x[0], x[1], x[2])):
        if i in used_g or j in used_p:
            continue
        used_g.add(i); used_p.add(j)
        due_ok = norm_due(pred[j].get("due")) == norm_due(gold[i]["due"])
        out["tp"] += 1; out["due_total"] += 1; out["due_correct"] += int(due_ok)
        out["matches"].append({"gold": i, "pred": j, "sim": round(sim, 3), "due_ok": due_ok})
    out["unmatched_pred"] = [j for j in range(len(pred)) if j not in used_p]
    out["unmatched_gold"] = [i for i in range(len(gold)) if i not in used_g]
    return out


def aggregate(per_row):
    tp = sum(r["tp"] for r in per_row); npred = sum(r["n_pred"] for r in per_row); ngold = sum(r["n_gold"] for r in per_row)
    p = tp / npred if npred else 0.0
    rc = tp / ngold if ngold else 0.0
    f1 = 2 * p * rc / (p + rc) if p + rc else 0.0
    due_total = sum(r["due_total"] for r in per_row)
    due_acc = sum(r["due_correct"] for r in per_row) / due_total if due_total else 0.0
    exact = sum(1 for r in per_row if r["valid"] and r["tp"] == r["n_gold"] == r["n_pred"] and r["due_correct"] == r["due_total"]) / len(per_row)
    return {"precision": round(p, 4), "recall": round(rc, 4), "f1": round(f1, 4), "due_acc": round(due_acc, 4),
            "exact_row_acc": round(exact, 4), "invalid": sum(1 for r in per_row if not r["valid"])}


# ---------------- unit tests ----------------
def _tests():
    gold = [{"owner": "Priya", "task": "draft the spec for the onboarding flow", "due": "Friday"},
            {"owner": "Tom", "task": "send the calendar invite for the retro", "due": None}]
    # 1. perfect answer, paraphrased task, "by Friday"
    r = score_rows(gold, '[{"owner":"Priya","task":"Draft onboarding flow spec","due":"by Friday"},{"owner":"Tom","task":"send calendar invite for the retro","due":null}]')
    assert (r["tp"], r["n_pred"], r["due_correct"]) == (2, 2, 2), r
    # 2. wrong answer: wrong owners -> must score 0 tp
    r = score_rows(gold, '[{"owner":"Marcus","task":"draft the spec for the onboarding flow","due":"Friday"}]')
    assert r["tp"] == 0 and r["n_pred"] == 1 and r["valid"], r
    # 3. invalid JSON -> invalid, zero preds
    r = score_rows(gold, "Here are the action items:\n- Priya: draft spec")
    assert r["valid"] is False and r["n_pred"] == 0 and r["tp"] == 0, r
    # 4. code-fenced + over-extraction (distractor) + wrong due -> 2 tp of 3 preds, 1 due correct
    r = score_rows(gold, '```json\n[{"owner":"Priya","task":"draft the onboarding spec","due":"Monday"},{"owner":"Tom","task":"send the retro invite","due":null},{"owner":"Elena","task":"look at the pricing page","due":null}]\n```')
    assert (r["tp"], r["n_pred"], r["due_correct"]) == (2, 3, 1), r
    # 5. one-to-one matching: two preds for the same gold only count once; wrapped in an object
    r = score_rows(gold, '{"action_items":[{"owner":"Priya","task":"draft the spec for onboarding","due":"Friday"},{"owner":"Priya","task":"draft onboarding flow spec v2","due":"Friday"}]}')
    assert (r["tp"], r["n_pred"]) == (1, 2), r
    agg = aggregate([score_rows(gold, '[]'), r])
    assert agg["invalid"] == 0 and agg["recall"] == 0.25, agg
    # due normalization
    assert norm_due("By the end of month.") == "end month" and norm_due("the end of the quarter") == norm_due("end of quarter") and norm_due("None") is None
    print("score.py: 5 unit tests passed")


if __name__ == "__main__":
    _tests()
