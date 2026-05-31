"""Tests for the Sentry -> Git owner Navigator agent."""
import app.agents.sentry_agent as sentry_module
from app.agents.sentry_agent import make_sentry_agent
from app.config import Settings
from app.coral import CoralError
from tests.conftest import FakeCoral, FakeLLM


def _use_settings(monkeypatch, **kwargs):
    monkeypatch.setattr(sentry_module, "get_settings", lambda: Settings(**kwargs))


async def test_sentry_agent_does_two_step_lookup(monkeypatch, fake_llm):
    _use_settings(monkeypatch, github_owner="acme", github_repo="webapp", sentry_project="api")
    # First query returns the issue (with faulting file); second finds the
    # commits that touched that file (the GitHub blame stand-in).
    coral = FakeCoral(rows_sequence=[
        [{"id": "E1", "title": "NPE", "culprit": "auth.login", "metadata_filename": "auth.py"}],
        [{"author_login": "alice", "sha": "abc123"}],
    ])
    node = make_sentry_agent(coral, fake_llm)

    update = await node({"event_type": "sentry_error", "raw_payload": {"error_id": "E1"}})

    assert update["sentry_context"] == "SUMMARY"
    assert len(coral.queries) == 2
    assert "sentry.issues" in coral.queries[0].lower()
    # Second step pivots to GitHub commit history for the faulting file.
    assert "github.commits" in coral.queries[1].lower()
    assert "auth.py" in coral.queries[1]


async def test_sentry_agent_skips_commit_lookup_when_no_issue_found(fake_llm):
    coral = FakeCoral(rows_sequence=[[]])  # no issue row
    node = make_sentry_agent(coral, fake_llm)

    update = await node({"raw_payload": {"error_id": "missing"}})

    assert len(coral.queries) == 1
    assert update["sentry_context"] == "SUMMARY"


async def test_sentry_agent_skips_commit_lookup_when_no_filename(fake_llm):
    # Issue found, but Sentry did not capture a faulting filename.
    coral = FakeCoral(rows_sequence=[[{"id": "E1", "title": "NPE", "metadata_filename": None}]])
    node = make_sentry_agent(coral, fake_llm)

    update = await node({"raw_payload": {"error_id": "E1"}})

    assert len(coral.queries) == 1
    assert update["sentry_context"] == "SUMMARY"


async def test_sentry_agent_handles_coral_error():
    coral = FakeCoral(raise_exc=CoralError("sentry unreachable"))
    node = make_sentry_agent(coral, FakeLLM())

    update = await node({"raw_payload": {"error_id": "E1"}})

    assert update["sentry_context"] == ""
    assert any("sentry" in e.lower() for e in update["errors"])
