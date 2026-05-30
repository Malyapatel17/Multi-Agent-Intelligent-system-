"""Tests for the Sentry -> Git Blame Navigator agent."""
from app.agents.sentry_agent import make_sentry_agent
from app.coral import CoralError
from tests.conftest import FakeCoral, FakeLLM


async def test_sentry_agent_does_two_step_lookup(fake_llm):
    # First query returns the error (with file/line); second returns blame.
    coral = FakeCoral(rows_sequence=[
        [{"id": "E1", "title": "NPE", "filename": "auth.py", "lineno": 42}],
        [{"author": "alice", "commit_sha": "abc123"}],
    ])
    node = make_sentry_agent(coral, fake_llm)

    update = await node({"event_type": "sentry_error", "raw_payload": {"error_id": "E1"}})

    assert update["sentry_context"] == "SUMMARY"
    assert len(coral.queries) == 2
    assert "sentry" in coral.queries[0].lower()
    assert "blame" in coral.queries[1].lower()


async def test_sentry_agent_skips_blame_when_no_error_found(fake_llm):
    coral = FakeCoral(rows_sequence=[[]])  # no error row
    node = make_sentry_agent(coral, fake_llm)

    update = await node({"raw_payload": {"error_id": "missing"}})

    # Only the first query runs; no blame lookup.
    assert len(coral.queries) == 1
    assert update["sentry_context"] == "SUMMARY"


async def test_sentry_agent_handles_coral_error():
    coral = FakeCoral(raise_exc=CoralError("sentry unreachable"))
    node = make_sentry_agent(coral, FakeLLM())

    update = await node({"raw_payload": {"error_id": "E1"}})

    assert update["sentry_context"] == ""
    assert any("sentry" in e.lower() for e in update["errors"])
