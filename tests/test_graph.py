"""End-to-end graph integration tests with fake Coral + LLM."""
from app.graph import build_graph
from tests.conftest import FakeCoral, FakeLLM


async def test_standup_flow_produces_summary_message():
    coral = FakeCoral(rows=[{"key": "DEV-1", "summary": "x"}])
    # Data agents return "DATA"; builder returns the final standup text.
    graph = build_graph(coral, FakeLLM(response="STANDUP TEXT"))

    result = await graph.ainvoke({
        "trigger_type": "on_demand",
        "event_type": "standup",
    })

    assert result["selected_agents"]
    assert result["final_message"] == "STANDUP TEXT"


async def test_sentry_webhook_flow_routes_to_sentry_only():
    coral = FakeCoral(rows_sequence=[
        [{"id": "E1", "filename": "a.py", "lineno": 5}],
        [{"author": "bob", "commit_sha": "deadbeef"}],
    ])
    graph = build_graph(coral, FakeLLM(response="BUG BRIEF"))

    result = await graph.ainvoke({
        "trigger_type": "webhook",
        "event_type": "sentry_error",
        "raw_payload": {"error_id": "E1"},
    })

    assert result["selected_agents"] == ["sentry_agent"]
    # Sentry context flows through to the final message (no standup synthesis).
    assert result["final_message"] == "BUG BRIEF"


async def test_unknown_event_produces_fallback_message():
    coral = FakeCoral(rows=[])
    graph = build_graph(coral, FakeLLM(response="nonsense"))

    result = await graph.ainvoke({
        "trigger_type": "on_demand",
        "user_text": "??",
    })

    assert result["selected_agents"] == []
    assert result["final_message"]  # non-empty fallback
