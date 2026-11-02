#!/usr/bin/env python3
"""pytest unit tests for ../score.py (the deterministic tool-pick scorer).

  cd submission/eval && python3 -m pytest test_score.py -v
"""
import os, sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
import score as sc


def test_exact_match():
    s = sc.score("gmail.send_email", "gmail.send_email")
    assert s["top1"] and s["top3"] and not s["invalid"] and s["pred"] == "gmail.send_email"


def test_case_and_whitespace_variance():
    s = sc.score("\n   GMAIL.Send_Email.  \n", "gmail.send_email")
    assert s["top1"] and s["pred"] == "gmail.send_email"


def test_wrong_tool_scores_zero():
    s = sc.score("gmail.create_draft", "gmail.send_email")
    assert not s["top1"] and not s["top3"] and not s["invalid"] and s["pred"] == "gmail.create_draft"


def test_unknown_tool_name_is_invalid():
    # looks like a tool name but is not in the 100-tool catalog: hallucination, counted invalid (and wrong)
    s = sc.score("gmail.send_mail", "gmail.send_email")
    assert s["invalid"] and s["pred"] == "invalid" and not s["top1"]


def test_empty_and_none_output_are_invalid():
    for raw in ("", None, "   "):
        s = sc.score(raw, "fs.read_file")
        assert s["invalid"] and s["pred"] == "invalid" and not s["top1"] and not s["top3"]


def test_json_wrapped_answer():
    s = sc.score('```json\n{"tool": "calendar.create_event", "reason": "user wants a meeting"}\n```', "calendar.create_event")
    assert s["top1"] and s["pred"] == "calendar.create_event"


def test_prose_without_catalog_name_is_invalid():
    s = sc.score("I would use the email sending tool for this.", "gmail.send_email")
    assert s["invalid"]


def test_think_block_is_ignored():
    s = sc.score("<think>could be jira.create_ticket or github.create_issue</think>\ngithub.create_issue", "github.create_issue")
    assert s["top1"] and s["ranked"][0] == "github.create_issue"


def test_ranked_list_top3_but_not_top1():
    s = sc.score("1. slack.send_message\n2. slack.reply_in_thread\n3. slack.schedule_message", "slack.reply_in_thread")
    assert not s["top1"] and s["top3"] and s["ranked"] == ["slack.send_message", "slack.reply_in_thread", "slack.schedule_message"]


def test_duplicates_deduped_and_order_kept():
    assert sc.parse("fs.read_file, fs.read_file, fs.write_file") == ["fs.read_file", "fs.write_file"]


def test_custom_catalog_argument():
    s = sc.score("foo.bar", "foo.bar", catalog=["foo.bar", "foo.baz"])
    assert s["top1"]
    assert sc.score("foo.bar", "foo.bar")["invalid"]  # not in the real catalog


if __name__ == "__main__":
    import pytest
    sys.exit(pytest.main([__file__, "-v"]))
