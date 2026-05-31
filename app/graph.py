"""LangGraph state graph assembly.

Wires the supervisor, the specialized agents, the standup builder, and the
formatter into a single executable graph.

Flow:

    START -> supervisor -> (Send) -> [jira_agent | pr_agent | sentry_agent]
                  |                              |
                  | (no data agents selected)    v
                  +------------------------> standup_builder -> formatter -> END

The supervisor's conditional routing fans out only to the data agents it
selected. Those agents converge on the standup builder (which synthesizes only
for standup requests, otherwise passes through), then the formatter assembles
the final Slack message.
"""
from __future__ import annotations

from langgraph.graph import END, START, StateGraph
from langgraph.types import Send

from app.agents.formatter import formatter_node
from app.agents.jira_agent import make_jira_agent
from app.agents.pr_agent import make_pr_agent
from app.agents.sentry_agent import make_sentry_agent
from app.agents.standup_builder import make_standup_builder
from app.coral import CoralClient
from app.identity import IdentityMap
from app.llm import LLM
from app.state import GraphState
from app.supervisor import make_supervisor

_DATA_AGENTS = {"jira_agent", "pr_agent", "sentry_agent"}


def _route_from_supervisor(state: GraphState):
    """Fan out to the selected data agents, or skip straight to formatting."""
    data_agents = [a for a in state.get("selected_agents", []) if a in _DATA_AGENTS]
    if not data_agents:
        return ["formatter"]
    return [Send(agent, state) for agent in data_agents]


def build_graph(coral: CoralClient, llm: LLM, identity: IdentityMap | None = None):
    """Build and compile the dev intelligence graph with injected deps."""
    builder = StateGraph(GraphState)

    builder.add_node("supervisor", make_supervisor(llm, identity))
    builder.add_node("jira_agent", make_jira_agent(coral, llm))
    builder.add_node("pr_agent", make_pr_agent(coral, llm))
    builder.add_node("sentry_agent", make_sentry_agent(coral, llm))
    builder.add_node("standup_builder", make_standup_builder(llm))
    builder.add_node("formatter", formatter_node)

    builder.add_edge(START, "supervisor")
    builder.add_conditional_edges(
        "supervisor",
        _route_from_supervisor,
        ["jira_agent", "pr_agent", "sentry_agent", "formatter"],
    )

    # Data agents converge on the standup builder (barrier sync), which either
    # synthesizes the standup or passes through.
    for agent in _DATA_AGENTS:
        builder.add_edge(agent, "standup_builder")
    builder.add_edge("standup_builder", "formatter")
    builder.add_edge("formatter", END)

    return builder.compile()
