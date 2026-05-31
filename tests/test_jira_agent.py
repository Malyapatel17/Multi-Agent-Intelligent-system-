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


async def test_jira_agent_queries_open_sprint_via_jql_filter(fake_llm):
    # The Coral jira source requires a `jql` filter; the agent must target the
    # open sprint through it (not a free-form `sprint = 'active'` clause).
    coral = FakeCoral(rows=[{"key": "DEV-1"}])
    node = make_jira_agent(coral, fake_llm)

    await node({"user_id": "U123"})

    query = coral.queries[0]
    assert "jql" in query
    assert "openSprints" in query
    # Uses the source's real column names.
    assert "status_name" in query
    assert "assignee_display_name" in query


async def test_jira_agent_scopes_to_assignee_when_identity_resolved(fake_llm):
    # When the supervisor resolved the triggering user's Jira accountId, the JQL
    # narrows to that assignee.
    coral = FakeCoral(rows=[{"key": "DEV-1"}])
    node = make_jira_agent(coral, fake_llm)

    await node({"user_id": "U123", "jira_account_id": "557058:abc"})

    query = coral.queries[0]
    assert "assignee =" in query
    assert "557058:abc" in query


async def test_jira_agent_no_assignee_clause_without_identity(fake_llm):
    coral = FakeCoral(rows=[{"key": "DEV-1"}])
    node = make_jira_agent(coral, fake_llm)

    await node({"user_id": "U123"})

    assert "assignee =" not in coral.queries[0]
