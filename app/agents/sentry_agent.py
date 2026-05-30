"""Sentry -> Git Blame Navigator agent.

Two-step lookup: fetch the Sentry error (with its faulting file/line), then run
a git blame query against GitHub to find the author and commit responsible.
Synthesizes an error -> owner -> suggested action briefing.
"""
from __future__ import annotations

from app.agents._common import error_update, format_rows
from app.coral import CoralClient, CoralError
from app.llm import LLM
from app.state import GraphState

SYSTEM_PROMPT = (
    "You are a bug triage assistant. Given a Sentry error and the git blame for "
    "the faulting line, identify who most likely owns the fix, summarize the "
    "error, and suggest a next action. Be concise and actionable."
)


def _error_query(error_id: str) -> str:
    return (
        "SELECT id, title, culprit, filename, lineno, last_seen "
        f"FROM sentry.errors WHERE id = '{error_id}'"
    )


def _blame_query(filename: str, lineno) -> str:
    return (
        "SELECT author, commit_sha, committed_at, message "
        f"FROM github.blame WHERE filename = '{filename}' AND lineno = {int(lineno)}"
    )


def make_sentry_agent(coral: CoralClient, llm: LLM):
    """Return a LangGraph node that produces ``sentry_context``."""

    async def sentry_agent(state: GraphState) -> dict:
        error_id = (state.get("raw_payload") or {}).get("error_id", "")
        try:
            errors = await coral.sql(_error_query(error_id))
            blame: list[dict] = []
            if errors:
                err = errors[0]
                filename = err.get("filename")
                lineno = err.get("lineno")
                if filename and lineno is not None:
                    blame = await coral.sql(_blame_query(filename, lineno))
        except CoralError as exc:
            return error_update("sentry_context", "sentry_agent", exc)

        prompt = (
            f"Sentry error:\n{format_rows(errors)}\n\n"
            f"Git blame for faulting line:\n{format_rows(blame)}"
        )
        summary = await llm.complete(system=SYSTEM_PROMPT, user=prompt)
        return {"sentry_context": summary}

    return sentry_agent
