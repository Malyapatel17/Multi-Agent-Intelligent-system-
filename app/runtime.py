"""Runtime container: wires the compiled graph to Slack delivery.

``Runtime.handle`` is the single code path both webhooks and Slack commands
funnel through — run the graph on the initial state, then post the resulting
message to Slack. ``build_runtime`` constructs the production runtime from
config (Coral + Claude + Slack).
"""
from __future__ import annotations

from app.coral import CoralClient
from app.graph import build_graph
from app.llm import AnthropicLLM
from app.slack import SlackNotifier


class Runtime:
    def __init__(self, graph, notifier: SlackNotifier):
        self._graph = graph
        self._notifier = notifier

    async def handle(self, state: dict) -> None:
        result = await self._graph.ainvoke(state)
        message = result.get("final_message", "")
        if message:
            await self._notifier.post(message, channel=state.get("slack_channel", ""))


def build_runtime() -> Runtime:
    """Construct the production runtime from environment configuration."""
    coral = CoralClient()
    llm = AnthropicLLM()
    graph = build_graph(coral, llm)
    notifier = SlackNotifier()
    return Runtime(graph, notifier)
