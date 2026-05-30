"""Tests for webhook / slash-command payload parsing into GraphState."""
from app.ingest import (
    parse_github_webhook,
    parse_sentry_webhook,
    parse_slash_command,
)


def test_parse_github_pr_opened():
    payload = {"action": "opened", "pull_request": {"number": 42}}

    state = parse_github_webhook(payload)

    assert state["trigger_type"] == "webhook"
    assert state["event_type"] == "pr_opened"
    assert state["raw_payload"]["pr_number"] == 42


def test_parse_github_non_opened_action_is_unknown():
    payload = {"action": "labeled", "pull_request": {"number": 7}}

    state = parse_github_webhook(payload)

    assert state["event_type"] == "unknown"


def test_parse_sentry_error():
    payload = {"data": {"error": {"id": "E-123"}}}

    state = parse_sentry_webhook(payload)

    assert state["trigger_type"] == "webhook"
    assert state["event_type"] == "sentry_error"
    assert state["raw_payload"]["error_id"] == "E-123"


def test_parse_slash_standup():
    form = {"command": "/standup", "text": "", "user_id": "U1", "channel_id": "C1"}

    state = parse_slash_command(form)

    assert state["trigger_type"] == "on_demand"
    assert state["event_type"] == "standup"
    assert state["user_id"] == "U1"
    assert state["slack_channel"] == "C1"


def test_parse_slash_bug_extracts_error_id():
    form = {"command": "/bug", "text": "E-999", "user_id": "U1", "channel_id": "C1"}

    state = parse_slash_command(form)

    assert state["event_type"] == "bug_query"
    assert state["raw_payload"]["error_id"] == "E-999"


def test_parse_slash_pr_extracts_number():
    form = {"command": "/pr", "text": "123", "user_id": "U1", "channel_id": "C1"}

    state = parse_slash_command(form)

    assert state["event_type"] == "pr_query"
    assert state["raw_payload"]["pr_number"] == 123


def test_parse_slash_unknown_command_falls_back_to_text():
    form = {"command": "/ask", "text": "who broke checkout?", "user_id": "U1", "channel_id": "C1"}

    state = parse_slash_command(form)

    # Left for the supervisor's LLM classifier; event_type not pre-set.
    assert state["user_text"] == "who broke checkout?"
    assert "event_type" not in state
