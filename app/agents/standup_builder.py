"""Standup Builder agent.

Aggregates the outputs of the other agents (Jira, PR, Sentry) into a single
coherent daily standup narrative. Does not touch Coral — it only synthesizes
context already gathered upstream.
"""
from __future__ import annotations

from app.llm import LLM
from app.state import GraphState

SYSTEM_PROMPT = (
    "You are a developer's standup assistant. Combine the provided Jira, PR, "
    "and bug context into a short daily standup: what's in progress, what needs "
    "review, and what's on fire. Use three labelled sections. Be concise."
)


def make_standup_builder(llm: LLM):
    """Return a LangGraph node that produces ``standup_summary``."""

    async def standup_builder(state: GraphState) -> dict:
        # The graph reaches this node via fan-in from the data agents, but it
        # should only synthesize when the supervisor actually selected it.
        selected = state.get("selected_agents")
        if selected is not None and "standup_builder" not in selected:
            return {}

        sections = []
        if state.get("jira_context"):
            sections.append(f"## Jira\n{state['jira_context']}")
        if state.get("pr_context"):
            sections.append(f"## PRs\n{state['pr_context']}")
        if state.get("sentry_context"):
            sections.append(f"## Bugs\n{state['sentry_context']}")

        user_prompt = "\n\n".join(sections) or "(no context gathered)"
        summary = await llm.complete(system=SYSTEM_PROMPT, user=user_prompt)
        return {"standup_summary": summary}

    return standup_builder
