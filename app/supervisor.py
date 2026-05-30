"""Supervisor node — the single orchestrator entry point.

The supervisor classifies the incoming request into an event type, then maps
that event type to the set of agents that should run. Webhook events arrive
already typed (set during payload parsing), so they route deterministically.
Free-form on-demand text is classified by Claude.
"""
from __future__ import annotations

from app.llm import LLM
from app.state import AgentName, EventType, GraphState

# Event type -> agents to invoke. The single source of routing truth.
ROUTING: dict[str, list[AgentName]] = {
    "standup": ["jira_agent", "pr_agent", "standup_builder"],
    "pr_opened": ["pr_agent"],
    "pr_query": ["pr_agent"],
    "sentry_error": ["sentry_agent"],
    "bug_query": ["sentry_agent"],
    "sprint_query": ["jira_agent"],
    "unknown": [],
}

_VALID_EVENTS = set(ROUTING.keys())

CLASSIFY_SYSTEM = (
    "Classify the developer's request into exactly one of these labels and "
    "reply with only the label, nothing else:\n"
    "- standup: a full daily summary of tickets, PRs, and bugs\n"
    "- sprint_query: a question about Jira tickets or sprint status\n"
    "- pr_query: a question about pull requests or reviews\n"
    "- bug_query: a question about an error, crash, or who caused a bug\n"
    "If none fit, reply: unknown"
)


def _normalize(label: str) -> EventType:
    cleaned = label.strip().lower().split()[0] if label.strip() else "unknown"
    return cleaned if cleaned in _VALID_EVENTS else "unknown"  # type: ignore[return-value]


def make_supervisor(llm: LLM):
    """Return the supervisor LangGraph node."""

    async def supervisor(state: GraphState) -> dict:
        event_type = state.get("event_type")

        # Classify free-form text when the event type isn't already known.
        if not event_type or event_type == "unknown":
            classified = await llm.complete(
                system=CLASSIFY_SYSTEM,
                user=state.get("user_text", ""),
            )
            event_type = _normalize(classified)

        return {
            "event_type": event_type,
            "selected_agents": ROUTING.get(event_type, []),
        }

    return supervisor
