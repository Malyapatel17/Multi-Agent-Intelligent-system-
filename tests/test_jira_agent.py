"""Tests for the Jira Ticket Intelligence agent."""
from app.agents.jira_agent import make_jira_agent
from app.coral import CoralError
from tests.conftest import FakeCoral, FakeLLM


async def test_jira_agent_queries_coral_and_summarizes(fake_llm):
    coral = FakeCoral(rows=[{"key": "DEV-1", "summary": "Fix login", "status": "In Progress"}])
    node = make_jira_agent(coral, fake_llm)

    update = await node({"user_id": "U123"})

    assert update["jira_context"] == "SUMMARY"
    assert coral.queries, "expected at least one Coral query"
    assert "jira" in coral.queries[0].lower()


async def test_jira_agent_feeds_rows_to_llm(fake_llm):
    coral = FakeCoral(rows=[{"key": "DEV-1", "summary": "Fix login"}])
    node = make_jira_agent(coral, fake_llm)

    await node({"user_id": "U123"})

    assert "DEV-1" in fake_llm.calls[0]["user"]


async def test_jira_agent_handles_coral_error_gracefully():
    coral = FakeCoral(raise_exc=CoralError("coral down"))
    node = make_jira_agent(coral, FakeLLM())

    update = await node({"user_id": "U123"})

    assert update["jira_context"] == ""
    assert any("jira" in e.lower() for e in update["errors"])
