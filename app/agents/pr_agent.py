"""PR Review Briefing agent.

Queries GitHub (via Coral) for open PRs — or a specific PR when triggered by a
webhook — and summarizes review status, reviewers, and related work.
"""
from __future__ import annotations

from app.agents._common import error_update, format_rows
from app.coral import CoralClient, CoralError
from app.llm import LLM
from app.state import GraphState

SYSTEM_PROMPT = (
    "You are a PR review briefing assistant. Given raw pull request rows, "
    "summarize each PR's title, author, review status, and assigned reviewers. "
    "Flag PRs waiting on review. Be concise."
)


def _build_query(state: GraphState) -> str:
    pr_number = (state.get("raw_payload") or {}).get("pr_number")
    base = (
        "SELECT number, title, author, state, requested_reviewers, updated "
        "FROM github.pulls"
    )
    if pr_number is not None:
        return f"{base} WHERE number = {int(pr_number)}"
    user_id = state.get("user_id")
    where = "state = 'open'"
    if user_id:
        where += f" AND author = '{user_id}'"
    return f"{base} WHERE {where} ORDER BY updated DESC"


def make_pr_agent(coral: CoralClient, llm: LLM):
    """Return a LangGraph node that produces ``pr_context``."""

    async def pr_agent(state: GraphState) -> dict:
        try:
            rows = await coral.sql(_build_query(state))
        except CoralError as exc:
            return error_update("pr_context", "pr_agent", exc)

        summary = await llm.complete(
            system=SYSTEM_PROMPT,
            user=f"Pull requests:\n{format_rows(rows)}",
        )
        return {"pr_context": summary}

    return pr_agent
