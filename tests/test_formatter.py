"""Tests for the Formatter node."""
from app.agents.formatter import formatter_node


async def test_formatter_uses_standup_summary_when_present():
    update = await formatter_node({
        "standup_summary": "Your standup",
        "jira_context": "ignored when standup present",
    })

    assert "Your standup" in update["final_message"]


async def test_formatter_falls_back_to_individual_contexts():
    update = await formatter_node({
        "sentry_context": "Bug owned by alice",
    })

    assert "Bug owned by alice" in update["final_message"]


async def test_formatter_appends_errors_note():
    update = await formatter_node({
        "pr_context": "PR brief",
        "errors": ["jira_agent: coral down"],
    })

    assert "PR brief" in update["final_message"]
    assert "coral down" in update["final_message"]


async def test_formatter_handles_no_content():
    update = await formatter_node({})

    assert update["final_message"]  # non-empty fallback message
