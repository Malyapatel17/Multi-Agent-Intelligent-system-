"""Tests for the PR Review Briefing agent."""
import app.agents.pr_agent as pr_module
from app.agents.pr_agent import make_pr_agent
from app.config import Settings
from app.coral import CoralError
from tests.conftest import FakeCoral, FakeLLM


def _use_settings(monkeypatch, **kwargs):
    monkeypatch.setattr(pr_module, "get_settings", lambda: Settings(**kwargs))


async def test_pr_agent_summarizes_open_prs(fake_llm):
    coral = FakeCoral(rows=[{"number": 42, "title": "Add caching", "state": "open"}])
    node = make_pr_agent(coral, fake_llm)

    update = await node({"user_id": "U1"})

    assert update["pr_context"] == "SUMMARY"
    assert "github.pulls" in coral.queries[0].lower()


async def test_pr_agent_scopes_to_configured_repo(monkeypatch, fake_llm):
    _use_settings(monkeypatch, github_owner="acme", github_repo="webapp")
    coral = FakeCoral(rows=[{"number": 1}])
    node = make_pr_agent(coral, fake_llm)

    await node({"user_id": "U1"})

    q = coral.queries[0]
    assert "owner = 'acme'" in q
    assert "repo = 'webapp'" in q


async def test_pr_agent_scopes_to_pr_number_from_webhook(fake_llm):
    coral = FakeCoral(rows=[{"number": 99, "title": "Fix bug"}])
    node = make_pr_agent(coral, fake_llm)

    await node({"event_type": "pr_opened", "raw_payload": {"pr_number": 99}})

    assert "99" in coral.queries[0]


async def test_pr_agent_scopes_to_author_when_identity_resolved(fake_llm):
    coral = FakeCoral(rows=[{"number": 1}])
    node = make_pr_agent(coral, fake_llm)

    await node({"user_id": "U1", "github_login": "octocat"})

    assert "author_login = 'octocat'" in coral.queries[0]


async def test_pr_agent_no_author_clause_without_identity(fake_llm):
    coral = FakeCoral(rows=[{"number": 1}])
    node = make_pr_agent(coral, fake_llm)

    await node({"user_id": "U1"})

    # author_login is always a selected column; assert it's not a WHERE predicate.
    assert "author_login =" not in coral.queries[0]


async def test_pr_agent_handles_coral_error():
    coral = FakeCoral(raise_exc=CoralError("boom"))
    node = make_pr_agent(coral, FakeLLM())

    update = await node({"user_id": "U1"})

    assert update["pr_context"] == ""
    assert any("pr" in e.lower() for e in update["errors"])
