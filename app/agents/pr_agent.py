"""PR Review Briefing agent.

Queries GitHub (via Coral) for open PRs — or a specific PR when triggered by a
webhook — and summarizes review status, reviewers, and related work.
"""
from __future__ import annotations

from app.agents._common import error_update, format_rows
from app.config import get_settings
from app.coral import CoralClient, CoralError
from app.llm import LLM
from app.state import GraphState

SYSTEM_PROMPT = (
    "You are a PR review briefing assistant. Given raw pull request rows, "
    "summarize each PR's title, author, review status, and assigned reviewers. "
    "Flag PRs waiting on review. Be concise."
)


def _build_query(state: GraphState) -> str:
    # owner/repo are required by the GitHub API and configured per deployment
    # (coral/sources/github.yaml). A future enhancement would read them from the
    # webhook payload to support multiple repos.
    cfg = get_settings()
    where = [f"owner = '{cfg.github_owner}'", f"repo = '{cfg.github_repo}'"]

    pr_number = (state.get("raw_payload") or {}).get("pr_number")
    if pr_number is not None:
        where.append(f"number = {int(pr_number)}")
    else:
        where.append("state = 'open'")
        # Scope to the triggering user's PRs when the supervisor resolved their
        # GitHub login (Coral applies this predicate over the returned rows).
        github_login = state.get("github_login")
        if github_login:
            where.append(f"author_login = '{github_login}'")
    return (
        "SELECT number, title, state, author_login, requested_reviewers, updated_at "
        "FROM github.pulls WHERE " + " AND ".join(where) + " ORDER BY updated_at DESC"
    )


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
