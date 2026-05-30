"""Tests for the Standup Builder agent."""
from app.agents.standup_builder import make_standup_builder
from tests.conftest import FakeLLM


async def test_standup_builder_combines_agent_outputs():
    llm = FakeLLM(response="Daily standup ready")
    node = make_standup_builder(llm)

    update = await node({
        "jira_context": "3 tickets in progress",
        "pr_context": "2 PRs awaiting review",
    })

    assert update["standup_summary"] == "Daily standup ready"
    user_prompt = llm.calls[0]["user"]
    assert "3 tickets in progress" in user_prompt
    assert "2 PRs awaiting review" in user_prompt


async def test_standup_builder_tolerates_missing_contexts():
    llm = FakeLLM(response="ok")
    node = make_standup_builder(llm)

    update = await node({"jira_context": "only jira"})

    assert update["standup_summary"] == "ok"


async def test_standup_builder_passes_through_when_not_selected():
    # When the supervisor did not select the builder, it must not summarize
    # (the graph reaches it via fan-in, but it should be a no-op).
    llm = FakeLLM(response="should not run")
    node = make_standup_builder(llm)

    update = await node({
        "selected_agents": ["sentry_agent"],
        "sentry_context": "bug info",
    })

    assert update == {}
    assert llm.calls == []


async def test_standup_builder_runs_when_selected():
    llm = FakeLLM(response="built")
    node = make_standup_builder(llm)

    update = await node({
        "selected_agents": ["jira_agent", "pr_agent", "standup_builder"],
        "jira_context": "j",
    })

    assert update["standup_summary"] == "built"
