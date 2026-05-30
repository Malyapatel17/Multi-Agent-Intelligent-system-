"""Tests for the PR Review Briefing agent."""
from app.agents.pr_agent import make_pr_agent
from app.coral import CoralError
from tests.conftest import FakeCoral, FakeLLM


async def test_pr_agent_summarizes_open_prs(fake_llm):
    coral = FakeCoral(rows=[{"number": 42, "title": "Add caching", "state": "open"}])
    node = make_pr_agent(coral, fake_llm)

    update = await node({"user_id": "U1"})

    assert update["pr_context"] == "SUMMARY"
    assert "github" in coral.queries[0].lower()


async def test_pr_agent_scopes_to_pr_number_from_webhook(fake_llm):
    coral = FakeCoral(rows=[{"number": 99, "title": "Fix bug"}])
    node = make_pr_agent(coral, fake_llm)

    await node({"event_type": "pr_opened", "raw_payload": {"pr_number": 99}})

    assert "99" in coral.queries[0]


async def test_pr_agent_handles_coral_error():
    coral = FakeCoral(raise_exc=CoralError("boom"))
    node = make_pr_agent(coral, FakeLLM())

    update = await node({"user_id": "U1"})

    assert update["pr_context"] == ""
    assert any("pr" in e.lower() for e in update["errors"])
