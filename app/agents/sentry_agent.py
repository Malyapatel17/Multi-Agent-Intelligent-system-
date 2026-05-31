"""Sentry -> Git owner Navigator agent.

Two-step lookup:

1. Fetch the Sentry issue (title, culprit, and the faulting file when Sentry
   captured it) from ``sentry.issues``.
2. If a faulting file is known, find the commits that touched it via
   ``github.commits`` (newest first) — the most recent author is the practical
   owner of the fix. (The GitHub REST API has no line-level blame, so file
   history is the honest stand-in.)

Synthesizes an error -> owner -> suggested action briefing.
"""
from __future__ import annotations

from app.agents._common import error_update, format_rows
from app.config import get_settings
from app.coral import CoralClient, CoralError
from app.llm import LLM
from app.state import GraphState

SYSTEM_PROMPT = (
    "You are a bug triage assistant. Given a Sentry issue and the recent commit "
    "history for the faulting file, identify who most likely owns the fix, "
    "summarize the error, and suggest a next action. Be concise and actionable."
)


def _issue_query(error_id: str, project: str) -> str:
    where = [f"project = '{project}'"]
    if error_id:
        where.append(f"id = '{error_id}'")
    return (
        "SELECT id, short_id, title, culprit, level, permalink, last_seen, "
        "metadata_filename FROM sentry.issues WHERE " + " AND ".join(where)
    )


def _commits_query(filename: str, owner: str, repo: str) -> str:
    return (
        "SELECT sha, author_name, author_login, committed_at, message "
        f"FROM github.commits WHERE owner = '{owner}' AND repo = '{repo}' "
        f"AND path = '{filename}'"
    )


def make_sentry_agent(coral: CoralClient, llm: LLM):
    """Return a LangGraph node that produces ``sentry_context``."""

    async def sentry_agent(state: GraphState) -> dict:
        cfg = get_settings()
        error_id = (state.get("raw_payload") or {}).get("error_id", "")
        try:
            issues = await coral.sql(_issue_query(error_id, cfg.sentry_project))
            commits: list[dict] = []
            if issues:
                filename = issues[0].get("metadata_filename")
                if filename:
                    commits = await coral.sql(
                        _commits_query(filename, cfg.github_owner, cfg.github_repo)
                    )
        except CoralError as exc:
            return error_update("sentry_context", "sentry_agent", exc)

        prompt = (
            f"Sentry issue:\n{format_rows(issues)}\n\n"
            f"Recent commits to the faulting file:\n{format_rows(commits)}"
        )
        summary = await llm.complete(system=SYSTEM_PROMPT, user=prompt)
        return {"sentry_context": summary}

    return sentry_agent
