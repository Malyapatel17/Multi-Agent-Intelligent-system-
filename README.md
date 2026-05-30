# Multi-Agent Dev Intelligence System

A multi-agent system that gives developers instant, context-rich intelligence from Jira, GitHub, and Sentry — delivered to Slack via on-demand queries or automatic event-driven triggers.

## Architecture Overview

```
┌──────────────────── Entry Points ──────────────────────┐
│                                                         │
│   User (Slack UI)           Webhooks                   │
│   "give me standup"     (GitHub PR, Sentry alert)      │
│         ↓                       ↓                      │
│         └───────────┬───────────┘                      │
│                     ↓                                   │
│            FastAPI  (receives both)                     │
└─────────────────────┬───────────────────────────────────┘
                      ↓
┌──────────── LangGraph State Graph ─────────────────────┐
│                                                         │
│              ★ SUPERVISOR AGENT ★                      │
│         (classifies intent from any source)             │
│                                                         │
│   On-demand path:        Event-driven path:             │
│   user asks → picks      webhook fires → picks          │
│   all agents +           only the relevant              │
│   standup builder        agent (e.g. Sentry)            │
│                                                         │
│      ↙         ↓         ↘         ↓                  │
│ [Jira]   [PR Review] [Sentry→Blame] [Standup Builder]  │
│      ↘         ↓         ↙         ↓                  │
│              Formatter Node                             │
│                   ↓                                     │
│             Post to Slack                               │
└────────────────────────────────────────────────────────┘
                      ↓
┌──────── Tool Layer (inside each agent) ────────────────┐
│          Coral MCP  →  Jira / GitHub / Sentry SQL      │
└────────────────────────────────────────────────────────┘
```

## System Layers

### 1. Data Sources
| Source | Data Available |
|--------|---------------|
| Jira | Tickets, sprints, epics, assignees |
| GitHub | PRs, commits, git blame |
| Sentry | Errors, stack traces |

### 2. Coral SQL Layer
Coral provides a unified SQL interface over all APIs — no ETL, no glue code. Each agent queries Jira, GitHub, or Sentry using plain SQL through Coral MCP tools.

### 3. Specialized Agents
| Agent | Responsibility | Data Used |
|-------|---------------|-----------|
| Jira Ticket Intelligence | Sprint status, ticket history, assignees | Jira |
| PR Review Briefing | Recent PRs, reviewer assignments, review status | GitHub |
| Sentry → Git Blame Navigator | Error → commit → author lookup | Sentry + GitHub |
| Standup Builder | Aggregates all agent outputs into a daily summary | All agents |

### 4. Supervisor Agent (Orchestrator)
The supervisor is the single entry point for all requests. It classifies the incoming intent and routes to the appropriate agents.

**Routing logic:**
| Trigger | Agents Invoked |
|---------|---------------|
| User: `/standup` or "give me summary" | Jira + PR + Standup Builder |
| GitHub webhook: PR opened | PR Review Agent |
| Sentry webhook: new error | Sentry → Git Blame Agent |
| User: "who caused this bug?" | Sentry → Git Blame Agent |
| User: "what's in my sprint?" | Jira Ticket Intel Agent |

### 5. Entry Points
| Entry Point | Trigger Type | Example |
|-------------|-------------|---------|
| Slack slash command | On-demand | `/standup`, `/bug`, `/pr` |
| Slack chat interface | On-demand | "Give me today's summary" |
| GitHub webhook | Event-driven | PR opened |
| Sentry webhook | Event-driven | New error alert |

### 6. Outputs (delivered to Slack)
| Output | Content |
|--------|---------|
| Standup Summary | Tickets in progress + recent PRs digest |
| Bug Report | Error → owner → suggested fix PR |
| PR Context Brief | Reviewer history + related past fixes |

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Agent Orchestration | [LangGraph](https://github.com/langchain-ai/langgraph) |
| API Server | FastAPI (Python) |
| LLM | Claude claude-sonnet-4-6 (Anthropic) |
| Data Access | Coral MCP (SQL over Jira, GitHub, Sentry) |
| Output | Slack SDK (Python) |
| Language | Python 3.11+ |

## Workflow

### On-Demand Flow (user triggers via Slack)
```
1. User sends /standup or natural language in Slack
2. FastAPI receives the Slack event/slash command
3. Supervisor Agent classifies intent
4. Supervisor fans out to: Jira Agent + PR Agent + Standup Builder (parallel)
5. Each agent queries Coral SQL for relevant data
6. Standup Builder aggregates results
7. Formatter Node structures the output
8. Slack message posted to the user/channel
```

### Event-Driven Flow (webhook triggers)
```
1. GitHub/Sentry/Jira fires a webhook (PR opened, error fired, ticket updated)
2. FastAPI receives and parses the webhook payload
3. Supervisor Agent classifies the event type
4. Supervisor routes to the single relevant agent
5. Agent queries Coral SQL for context
6. Formatter Node structures the output
7. Slack message posted as an alert to the relevant channel
```

## Getting Started

```bash
# 1. Create a virtual environment and install dependencies
python -m venv .venv
.venv/Scripts/activate        # Windows
# source .venv/bin/activate   # macOS / Linux
pip install -r requirements-dev.txt

# 2. Configure credentials (fill in real values)
cp .env.example .env

# 3. Run the tests
pytest

# 4. Start the API server
uvicorn app.main:app --reload
```

> Credentials in `.env` are read lazily — the code, tests, and graph all run
> without real keys. Provide keys only when connecting to live Coral, Claude,
> and Slack.

## Endpoints

| Method | Path | Purpose |
|--------|------|---------|
| GET | `/health` | Liveness check |
| POST | `/webhooks/github` | GitHub PR events (event-driven) |
| POST | `/webhooks/sentry` | Sentry error events (event-driven) |
| POST | `/slack/command` | Slack slash commands `/standup`, `/bug`, `/pr` (on-demand) |

## Project Layout

```
app/
├── main.py            # FastAPI app + endpoints
├── runtime.py         # Wires graph → Slack delivery
├── graph.py           # LangGraph state graph assembly
├── supervisor.py      # Intent classification + routing
├── state.py           # GraphState (shared typed state)
├── coral.py           # Coral SQL tool layer
├── llm.py             # Claude wrapper
├── slack.py           # Slack delivery
├── ingest.py          # Webhook / slash-command parsers
└── agents/            # jira, pr, sentry, standup_builder, formatter
tests/                 # Full pytest suite (TDD)
```

## Design Spec

See [`docs/design-spec.md`](docs/design-spec.md) for the full design specification.
