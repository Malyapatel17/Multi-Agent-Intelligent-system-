"""Shared LangGraph state for the multi-agent dev intelligence system.

Every node reads from and writes to this single typed state dict. There is no
hidden state between agents — all data flows through GraphState.
"""
from __future__ import annotations

import operator
from typing import Annotated, Literal

from typing_extensions import TypedDict

TriggerType = Literal["on_demand", "webhook"]

EventType = Literal[
    "standup",        # full daily summary
    "pr_opened",      # GitHub webhook: a PR was opened
    "pr_query",       # on-demand PR question
    "sentry_error",   # Sentry webhook: a new error fired
    "bug_query",      # on-demand bug/error question
    "sprint_query",   # on-demand Jira/sprint question
    "unknown",        # supervisor could not classify
]

# Node names the supervisor can route to. Used as the canonical agent registry.
AgentName = Literal[
    "jira_agent",
    "pr_agent",
    "sentry_agent",
    "standup_builder",
]


class GraphState(TypedDict, total=False):
    # --- Routing inputs ---
    trigger_type: TriggerType
    event_type: EventType
    raw_payload: dict
    user_text: str          # free-form text from chat or slash command args
    user_id: str            # Slack user who triggered (on-demand)
    slack_channel: str      # where to post the output

    # --- Supervisor decision ---
    selected_agents: list[AgentName]

    # --- Agent outputs ---
    jira_context: str
    pr_context: str
    sentry_context: str
    standup_summary: str

    # --- Final delivery ---
    final_message: str

    # --- Non-fatal errors accumulated across nodes ---
    # Annotated with operator.add so parallel agent nodes can each append
    # without clobbering one another.
    errors: Annotated[list[str], operator.add]
