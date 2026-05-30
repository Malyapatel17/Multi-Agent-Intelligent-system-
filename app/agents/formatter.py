"""Formatter node.

Assembles the final Slack-ready message from whichever context fields the
upstream agents populated. Deterministic — no LLM call — so output is
predictable and cheap. Prefers the aggregated standup summary; otherwise falls
back to the individual agent contexts that ran.
"""
from __future__ import annotations

from app.state import GraphState

_FALLBACK = "No intelligence could be gathered for this request."


async def formatter_node(state: GraphState) -> dict:
    if state.get("standup_summary"):
        body = state["standup_summary"]
    else:
        parts = [
            state[key]
            for key in ("jira_context", "pr_context", "sentry_context")
            if state.get(key)
        ]
        body = "\n\n".join(parts) if parts else _FALLBACK

    errors = state.get("errors") or []
    if errors:
        note = "\n".join(f"- {e}" for e in errors)
        body = f"{body}\n\n_Some data was unavailable:_\n{note}"

    return {"final_message": body}
