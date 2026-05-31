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

The app reaches Coral by launching the CLI as an **MCP stdio subprocess**
(`coral mcp-stdio`) and calling its `sql` tool — there is no HTTP endpoint. The
transport lives in [`app/coral.py`](app/coral.py) behind an injectable
`CoralTransport` protocol, so the whole system tests against a fake.

**Source specs** live in [`coral/`](coral/) — one per data source, so the agents
run on real data instead of illustrative SQL:

| Spec | Tables | Powers |
|------|--------|--------|
| [`jira.yaml`](coral/sources/jira.yaml) ⭐ | `jira.issues` (JQL, cursor pages) | Jira agent |
| [`github.yaml`](coral/sources/github.yaml) | `github.pulls`, `github.commits` | PR agent + Sentry owner lookup |
| [`sentry.yaml`](coral/sources/sentry.yaml) | `sentry.issues` | Sentry agent |

⭐ = the bonus from the architecture diagram. See [`coral/README.md`](coral/README.md)
for setup and validation of each.

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
| Data Access | Coral MCP (SQL over Jira, GitHub, Sentry) via `coral mcp-stdio` |
| Output | Slack SDK (Python) |
| Language | Python 3.10+ |

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

## Security

All three POST endpoints verify the inbound request signature before doing any
work (HMAC-SHA256, constant-time comparison):

| Provider | Header | Scheme |
|----------|--------|--------|
| Slack | `X-Slack-Signature` + `X-Slack-Request-Timestamp` | `v0=<hmac>` over `v0:{ts}:{body}`, 5-min replay window |
| GitHub | `X-Hub-Signature-256` | `sha256=<hmac>` over raw body |
| Sentry | `Sentry-Hook-Signature` | bare hex `<hmac>` over raw body |

Verification is **skipped when the corresponding secret is unset** (`.env`),
so local development and tests run without signatures. Set
`SLACK_SIGNING_SECRET`, `GITHUB_WEBHOOK_SECRET`, and `SENTRY_WEBHOOK_SECRET`
in production to enforce it.

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
├── security.py        # Slack / GitHub / Sentry signature verification
├── identity.py        # Slack user → Jira accountId / GitHub login mapping
└── agents/            # jira, pr, sentry, standup_builder, formatter
tests/                 # Full pytest suite (TDD)
```

## Per-user scoping (identity map)

A Slack user ID is not a Jira `accountId` or a GitHub login, so to answer "what's
in *my* sprint?" the supervisor translates the triggering Slack user via
[`app/identity.py`](app/identity.py) and writes the resolved IDs into state.
The Jira and PR agents then narrow their queries (`assignee = …`,
`author_login = …`). Configure the map with the `IDENTITY_MAP` env var (JSON);
unmapped users transparently fall back to unscoped queries.

## Deployment

See [`docs/deployment.md`](docs/deployment.md) for Docker/host setup, exposing a
public URL, loading the Coral sources, and registering the Slack/GitHub/Sentry
endpoints.

## Design Spec

See [`docs/design-spec.md`](docs/design-spec.md) for the full design specification.
