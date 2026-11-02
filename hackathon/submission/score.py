#!/usr/bin/env python3
"""Deterministic scorer for tool picks. `python3 score.py --test` runs the unit tests."""
import json, re, os, sys
HERE = os.path.dirname(os.path.abspath(__file__))
CATALOG = [t["name"] for t in json.load(open(os.path.join(HERE, "data", "catalog.json")))]
_CAT = {c.lower(): c for c in CATALOG}
_NAME_RE = re.compile(r"[a-z0-9_]+\.[a-z0-9_]+", re.I)

def parse(raw, catalog=None):
    """Return the ranked list of valid catalog names found in a model output (deduped, in order)."""
    cat = {c.lower(): c for c in catalog} if catalog else _CAT
    if not raw:
        return []
    if "</think>" in raw:
        raw = raw.split("</think>")[-1]
    out = []
    for m in _NAME_RE.findall(raw):
        n = cat.get(m.lower())
        if n and n not in out:
            out.append(n)
    return out

def score(raw, gold, catalog=None):
    ranked = parse(raw, catalog)
    pred = ranked[0] if ranked else "invalid"
    return {"pred": pred, "ranked": ranked[:3], "top1": pred == gold, "top3": gold in ranked[:3], "invalid": not ranked}

def _test():
    cases = [
        ("calendar.update_event", "calendar.update_event", True, True, False),
        ("  Calendar.Update_Event. ", "calendar.update_event", True, True, False),            # case + punctuation
        ('{"tool": "gmail.reply_to_email"}', "gmail.reply_to_email", True, True, False),       # JSON wrapper
        ("1. slack.send_message\n2. slack.reply_in_thread\n3. slack.schedule_message", "slack.reply_in_thread", False, True, False),  # top-3 hit, top-1 miss
        ("calendar.create_event", "reminders.create", False, False, False),                   # wrong answer scores 0
        ("I would use the email sender tool", "gmail.send_email", False, False, True),         # invalid: no catalog name
        ("<think>maybe jira.create_ticket</think>\ngithub.create_issue", "github.create_issue", True, True, False),  # ignore think block
        ("", "fs.read_file", False, False, True),                                              # empty output
        ("slack.post_message", "slack.send_message", False, False, True),                     # hallucinated name is invalid
    ]
    for raw, gold, t1, t3, inv in cases:
        s = score(raw, gold)
        assert (s["top1"], s["top3"], s["invalid"]) == (t1, t3, inv), (raw, s)
    print(f"score.py: {len(cases)} unit tests passed")

if __name__ == "__main__":
    _test()
