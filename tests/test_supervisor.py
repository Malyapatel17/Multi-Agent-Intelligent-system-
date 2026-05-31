"""Tests for the Supervisor routing node."""
from app.identity import IdentityMap
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


async def test_supervisor_resolves_triggering_user_identity():
    identity = IdentityMap(
        slack_to_jira={"U1": "557058:abc"},
        slack_to_github={"U1": "octocat"},
    )
    node = make_supervisor(FakeLLM(), identity)

    update = await node({"event_type": "standup", "user_id": "U1"})

    assert update["jira_account_id"] == "557058:abc"
    assert update["github_login"] == "octocat"


async def test_supervisor_omits_identity_for_unmapped_user():
    node = make_supervisor(FakeLLM(), IdentityMap(slack_to_jira={"U1": "x"}))

    update = await node({"event_type": "standup", "user_id": "U-unknown"})

    assert "jira_account_id" not in update
    assert "github_login" not in update
