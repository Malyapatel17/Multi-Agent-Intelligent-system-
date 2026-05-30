"""Jira Ticket Intelligence agent.

Queries Jira (via Coral) for the active sprint and synthesizes a summary of
ticket status, assignees, and blockers.
"""
from __future__ import annotations

from app.agents._common import error_update, format_rows
from app.coral import CoralClient, CoralError
from app.llm import LLM
from app.state import GraphState

SYSTEM_PROMPT = (
    "You are a Jira ticket intelligence assistant. Given raw sprint ticket "
    "rows, write a concise summary of what is in progress, what is blocked, "
    "and who is working on what. Use short bullet points."
)


def _build_query(state: GraphState) -> str:
    user_id = state.get("user_id")
    where = "sprint = 'active'"
    if user_id:
        where += f" AND assignee = '{user_id}'"
    return (
        "SELECT key, summary, status, assignee, updated "
        f"FROM jira.issues WHERE {where} ORDER BY updated DESC"
    )


def make_jira_agent(coral: CoralClient, llm: LLM):
    """Return a LangGraph node that produces ``jira_context``."""

    async def jira_agent(state: GraphState) -> dict:
        try:
            rows = await coral.sql(_build_query(state))
        except CoralError as exc:
            return error_update("jira_context", "jira_agent", exc)

        summary = await llm.complete(
            system=SYSTEM_PROMPT,
            user=f"Sprint tickets:\n{format_rows(rows)}",
        )
        return {"jira_context": summary}

    return jira_agent
