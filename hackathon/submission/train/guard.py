#!/usr/bin/env python3
"""Deterministic snap-to-catalog guardrail, applied at scoring/serving time.

If the model's output is not an exact catalog name, snap to the closest catalog name by string similarity
(difflib.SequenceMatcher ratio on lowercased names) when the best ratio is >= 0.8; otherwise keep it invalid.
Rescores a results JSON from tune.py and writes <name>_guard.json with the same shape plus a `guardrail` block.

  python3 guard.py results/sft_nocatalog.json          # -> results/sft_nocatalog_guard.json
  python3 guard.py --test                              # unit tests
"""
import difflib, json, os, sys

HERE = os.path.dirname(os.path.abspath(__file__))
SUB = os.path.dirname(HERE)
sys.path.insert(0, SUB)
import score  # noqa: E402

CATALOG = score.CATALOG
THRESH = 0.8


def snap(raw, catalog=CATALOG, thresh=THRESH):
    """Return (pred, snapped: bool, ratio). Exact catalog hits pass through score.parse; otherwise nearest name if ratio >= thresh."""
    ranked = score.parse(raw, catalog)
    if ranked:
        return ranked[0], False, 1.0
    text = (raw or "").split("</think>")[-1]
    m = score._NAME_RE.search(text)
    cand = (m.group(0) if m else text).strip().strip(".").lower()
    if not cand:
        return "invalid", False, 0.0
    best, best_r = None, 0.0
    for c in catalog:
        r = difflib.SequenceMatcher(None, cand, c.lower()).ratio()
        if r > best_r:
            best, best_r = c, r
    if best_r >= thresh:
        return best, True, round(best_r, 3)
    return "invalid", False, round(best_r, 3)


def rescore(path):
    d = json.load(open(path))
    snapped, fixed, broke = 0, 0, 0
    for r in d["rows"]:
        pred, was_snapped, ratio = snap(r["raw"])
        r["pred_guard"], r["snapped"], r["snap_ratio"] = pred, was_snapped, ratio
        r["correct_guard"] = pred == r["gold"]
        if was_snapped:
            snapped += 1
            fixed += int(r["correct_guard"] and not r["correct"])
            broke += int(r["correct"] and not r["correct_guard"])
    n = len(d["rows"])
    d["guardrail"] = {"rule": f"snap to nearest catalog name when SequenceMatcher ratio >= {THRESH}", "snapped": snapped,
                      "fixed": fixed, "broke": broke, "accuracy_without": d["accuracy"],
                      "invalid_without": d["invalid_outputs"]}
    d["accuracy"] = round(sum(r["correct_guard"] for r in d["rows"]) / n, 4)
    d["invalid_outputs"] = sum(r["pred_guard"] == "invalid" for r in d["rows"])
    d["prompt"] = d.get("prompt", "") + "+guardrail"
    out = path.replace(".json", "_guard.json")
    json.dump(d, open(out, "w"), indent=1, ensure_ascii=False)
    print(f"{os.path.basename(path)}: {d['guardrail']['accuracy_without']:.1%} -> {d['accuracy']:.1%} with guardrail "
          f"(snapped {snapped}, fixed {fixed}, broke {broke}, invalid {d['guardrail']['invalid_without']} -> {d['invalid_outputs']}); saved {out}")
    for r in d["rows"]:
        if r["snapped"]:
            print(f"   {r['id']} {r['raw'].split('<|eot|>')[0][:40]!r} -> {r['pred_guard']} ({r['snap_ratio']}) {'✓' if r['correct_guard'] else '✗'}")


def _test():
    assert snap("db.query<|eot|>") == ("db.run_query", True, 0.8)                 # snapped at exactly the threshold
    assert snap("jira.move_ticket<|eot|>") == ("invalid", False, 0.765)            # below 0.8 stays invalid (no test-set tuning)
    assert snap("calendar.update_event_response")[0] == "calendar.update_event"
    assert snap("calendar.update_event")[0:2] == ("calendar.update_event", False)
    assert snap("I would use the email tool")[0] == "invalid"
    assert snap("")[0] == "invalid"
    print("guard.py: 5 unit tests passed")


if __name__ == "__main__":
    if "--test" in sys.argv:
        _test()
    else:
        for p in sys.argv[1:]:
            rescore(p)
