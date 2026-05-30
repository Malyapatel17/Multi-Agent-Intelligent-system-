# Design Specification — Multi-Agent Dev Intelligence System

**Date:** 2026-05-23
**Status:** Approved

---

## 1. Problem Statement

Developers lose time context-switching between Jira, GitHub, and Sentry to assemble their daily picture — what tickets are in progress, what PRs need attention, and which errors need fixing. This system automates that intelligence gathering and delivers it to Slack, either on-demand or automatically when relevant events occur.

---

## 2. Goals

- Generate a daily standup summary on demand from Slack
- Automatically surface PR context when a PR is opened
- Automatically trace Sentry errors to the responsible commit/author
- Keep all data access through a single SQL abstraction (Coral) — no direct API calls per agent

---

## 3. Architecture

### 3.1 Framework Choice: LangGraph

LangGraph is chosen over CrewAI because:
- Native support for conditional routing between agents based on event type
- Parallel agent execution via `Send` API (fan-out pattern)
- Typed shared state (`GraphState`) visible to all nodes
- Async-first — fits both webhook and on-demand trigger models
- Better observability and retry handling than CrewAI

### 3.2 System Components

```
FastAPI App
  └── /slack/events     (Slack slash commands + chat messages)
  └── /webhooks/github  (PR opened, merged, etc.)
  └── /webhooks/sentry  (new error, regression)

LangGraph Graph
  └── supervisor_node       — classifies intent, routes to agents
  └── jira_agent_node       — queries Jira via Coral
  └── pr_agent_node         — queries GitHub via Coral
  └── sentry_agent_node     — queries Sentry + GitHub blame via Coral
  └── standup_builder_node  — aggregates multi-agent output
  └── formatter_node        — structures final Slack message

Coral MCP
  └── Tool: sql(query)      — unified SQL interface to all sources

Slack SDK
  └── post_message()        — delivers output to channel or DM
```

---

## 4. Data Flow

### 4.1 Shared Graph State

```python
class GraphState(TypedDict):
    trigger_type: str          # "on_demand" | "webhook"
    event_type: str            # "standup" | "pr_opened" | "sentry_error" | ...
    raw_payload: dict          # original request payload
    user_id: str               # Slack user who triggered (if on-demand)
    slack_channel: str         # where to post the output
    jira_context: str          # output from Jira agent
    pr_context: str            # output from PR agent
    sentry_context: str        # output from Sentry agent
    standup_summary: str       # output from Standup Builder
    final_message: str         # formatted Slack message
    errors: list[str]          # any agent errors (non-fatal)
```

### 4.2 On-Demand Flow

```
Slack → FastAPI → GraphState(trigger="on_demand", event="standup")
  → supervisor_node: routes to [jira_agent, pr_agent, standup_builder]
  → parallel Send: jira_agent + pr_agent run simultaneously
  → standup_builder_node: reads jira_context + pr_context, writes standup_summary
  → formatter_node: writes final_message
  → Slack post to user_id channel
```

### 4.3 Event-Driven Flow

```
GitHub webhook → FastAPI → GraphState(trigger="webhook", event="pr_opened")
  → supervisor_node: routes only to pr_agent
  → pr_agent_node: queries Coral for PR reviewers, related commits
  → formatter_node: writes final_message
  → Slack post to engineering channel
```

---

## 5. Agent Specifications

### 5.1 Supervisor Agent
- **Input:** `GraphState.raw_payload` + `GraphState.trigger_type`
- **Responsibility:** Classify intent → return list of agent node names to invoke
- **Logic:** Uses Claude with a system prompt describing all event types and agent mappings
- **Output:** LangGraph `Send` commands to selected agent nodes

### 5.2 Jira Ticket Intelligence Agent
- **Input:** User ID or team name from state
- **Coral queries:** Active sprint tickets, ticket history, assignees, blocked tickets
- **Output:** `GraphState.jira_context` — structured text summary of sprint state
- **Tool:** `coral.sql("SELECT * FROM jira.issues WHERE sprint = current AND assignee = ...")`

### 5.3 PR Review Briefing Agent
- **Input:** PR number (webhook) or user ID (on-demand)
- **Coral queries:** Open PRs, reviewer assignments, review comments, related commits
- **Output:** `GraphState.pr_context` — PR status and reviewer summary
- **Tool:** `coral.sql("SELECT * FROM github.pulls WHERE state = 'open' ...")`

### 5.4 Sentry → Git Blame Navigator Agent
- **Input:** Sentry error ID or error message from webhook
- **Coral queries:** Error details + stack trace → file/line → git blame → commit → author
- **Output:** `GraphState.sentry_context` — error owner, commit, suggested action
- **Tool:** Two-step Coral query: `sentry.errors` → `github.blame`

### 5.5 Standup Builder Agent
- **Input:** `jira_context` + `pr_context` + `sentry_context` from state
- **Responsibility:** Synthesize all agent outputs into a coherent daily standup narrative
- **Output:** `GraphState.standup_summary`
- **Note:** Only invoked on on-demand standup requests, not on individual webhooks

### 5.6 Formatter Node
- **Input:** The relevant context field(s) depending on which agents ran
- **Responsibility:** Format output as Slack Block Kit message (sections, bullet points)
- **Output:** `GraphState.final_message` — Slack-ready JSON payload

---

## 6. Entry Points

### 6.1 Slack Slash Commands
- `/standup` — triggers on-demand full summary
- `/bug <error-id>` — triggers Sentry agent for a specific error
- `/pr <pr-number>` — triggers PR agent for a specific PR

### 6.2 Slack Chat (Natural Language)
- FastAPI handles `message` events from Slack
- Supervisor agent classifies free-form text to determine intent
- Same routing logic as slash commands

### 6.3 Webhooks
- `POST /webhooks/github` — payload parsed for event type (PR opened, merged, review requested)
- `POST /webhooks/sentry` — payload parsed for error ID and severity
- Webhook secret validation on all endpoints

---

## 7. Error Handling

- Each agent node catches exceptions and writes to `GraphState.errors` — graph continues
- If a critical agent fails (e.g., Coral unreachable), supervisor posts a partial result with an error note to Slack
- Webhook endpoints return HTTP 200 immediately and process async (no timeout risk)
- LangGraph retry policy: 2 retries with exponential backoff per node

---

## 8. Testing Strategy

- **Unit:** Each agent node tested with mocked Coral responses
- **Integration:** FastAPI test client sends mock Slack payloads and webhook payloads; assert correct agents are invoked via state inspection
- **E2E:** Full graph run against a staging Coral instance connected to test Jira/GitHub/Sentry projects

---

## 9. Project Structure

```
malya_patel/
├── app/
│   ├── main.py              # FastAPI app, routes
│   ├── graph.py             # LangGraph graph definition
│   ├── state.py             # GraphState TypedDict
│   ├── supervisor.py        # Supervisor node
│   └── agents/
│       ├── jira_agent.py
│       ├── pr_agent.py
│       ├── sentry_agent.py
│       ├── standup_builder.py
│       └── formatter.py
├── docs/
│   ├── design-spec.md       # this file
│   └── architecture.svg     # visual diagram
├── tests/
│   ├── test_supervisor.py
│   ├── test_agents.py
│   └── test_webhooks.py
├── requirements.txt
└── README.md
```
