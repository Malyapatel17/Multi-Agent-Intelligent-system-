"""Tests for the Supervisor routing node."""
from app.supervisor import make_supervisor
from tests.conftest import FakeLLM


async def test_webhook_pr_opened_routes_to_pr_agent_only():
    node = make_supervisor(FakeLLM())

    update = await node({"trigger_type": "webhook", "event_type": "pr_opened"})

    assert update["selected_agents"] == ["pr_agent"]


async def test_webhook_sentry_error_routes_to_sentry_agent_only():
    node = make_supervisor(FakeLLM())

    update = await node({"trigger_type": "webhook", "event_type": "sentry_error"})

    assert update["selected_agents"] == ["sentry_agent"]


async def test_standup_routes_to_jira_pr_and_builder():
    node = make_supervisor(FakeLLM())

    update = await node({"trigger_type": "on_demand", "event_type": "standup"})

    assert set(update["selected_agents"]) == {"jira_agent", "pr_agent", "standup_builder"}


async def test_freeform_text_is_classified_by_llm():
    # LLM classifies the free-form question as a bug query.
    node = make_supervisor(FakeLLM(response="bug_query"))

    update = await node({
        "trigger_type": "on_demand",
        "user_text": "who caused the checkout crash?",
    })

    assert update["event_type"] == "bug_query"
    assert update["selected_agents"] == ["sentry_agent"]


async def test_unknown_classification_selects_no_agents():
    node = make_supervisor(FakeLLM(response="nonsense"))

    update = await node({"trigger_type": "on_demand", "user_text": "??"})

    assert update["event_type"] == "unknown"
    assert update["selected_agents"] == []
