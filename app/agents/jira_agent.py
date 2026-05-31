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


def _build_jql(state: GraphState) -> str:
    """Build the JQL string for the active sprint.

    When the supervisor resolved the triggering Slack user to a Jira accountId
    (via the IdentityMap), scope to that assignee — otherwise summarize the whole
    active sprint.
    """
    clauses = ["sprint in openSprints()"]
    account_id = state.get("jira_account_id")
    if account_id:
        clauses.append(f"assignee = '{account_id}'")
    return " AND ".join(clauses) + " ORDER BY updated DESC"


def _build_query(state: GraphState) -> str:
    # The Coral `jira` source (coral/sources/jira.yaml) exposes a JQL-filtered
    # `issues` table; `jql` is a required filter. Column names match the source.
    jql = _build_jql(state).replace("'", "''")
    return (
        "SELECT key, summary, status_name, assignee_display_name, updated "
        f"FROM jira.issues WHERE jql = '{jql}'"
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
