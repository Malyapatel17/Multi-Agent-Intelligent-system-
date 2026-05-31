# Deployment Guide

This covers everything between "tests pass locally" and "the bot answers in
Slack". The app itself is a single FastAPI service; the moving parts around it
are **Coral** (the data layer) and the three **provider webhooks/commands**.

## Architecture recap

```
GitHub / Sentry / Slack  ──HTTPS──▶  FastAPI (this app)  ──stdio──▶  coral mcp-stdio
                                          │                              │
                                          └──────────▶ Claude            └─▶ Jira / GitHub / Sentry APIs
                                          └──────────▶ Slack post
```

The app launches the **Coral CLI as a subprocess** (`coral mcp-stdio`) and calls
its `sql` tool over MCP. So wherever the app runs, the `coral` binary must be on
`PATH` and configured with source credentials.

## 1. Run with Docker (recommended)

The image bundles both the app and the Coral CLI.

```bash
docker build -t dev-intel-agents .
docker run --rm -p 8000:8000 --env-file .env dev-intel-agents
```

> The Coral CLI needs its own credentials/onboarding inside the container
> (`coral onboard`, source tokens). For a real deployment, either bake an
> onboarded Coral config into the image or mount it as a volume
> (`-v $HOME/.coral:/root/.coral`). See [Coral env](#4-coral-data-layer).

## 2. Run without Docker

```bash
python -m venv .venv && . .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt
# Install the Coral CLI (https://withcoral.com/docs/getting-started/installation)
curl -fsSL https://withcoral.com/install.sh | sh    # or: brew install withcoral/tap/coral
coral onboard

cp .env.example .env   # fill in values
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

## 3. Expose a public URL

Webhooks from GitHub/Sentry and Slack slash commands must reach the service over
HTTPS. Options:

- **Local dev:** `ngrok http 8000` → use the `https://….ngrok.app` URL below.
- **Cloud:** any platform that gives you an HTTPS endpoint (Fly.io, Render, Cloud
  Run, ECS, a VM behind a load balancer). The container listens on `:8000`.

## 4. Coral (data layer)

Coral holds the **source credentials** (Jira/GitHub/Sentry tokens) in *its* own
environment — not this app's `.env`. Load the three source specs and provide
their inputs:

```bash
export JIRA_BASE_URL=... JIRA_EMAIL=... JIRA_API_TOKEN=...
export GITHUB_TOKEN=...
export SENTRY_ORG=... SENTRY_TOKEN=...

coral source add --file ./coral/sources/jira.yaml
coral source add --file ./coral/sources/github.yaml
coral source add --file ./coral/sources/sentry.yaml
coral source lint ./coral/sources/*.yaml   # validate
```

See [`coral/README.md`](../coral/README.md) for per-source detail and smoke-test
queries.

## 5. Register the providers

| Provider | Where | Point at | Secret env var |
|----------|-------|----------|----------------|
| **Slack** | api.slack.com/apps → your app → Slash Commands | `https://<host>/slack/command` | `SLACK_SIGNING_SECRET` |
| **GitHub** | Repo → Settings → Webhooks → Add | `https://<host>/webhooks/github` (content type `application/json`, event: Pull requests) | `GITHUB_WEBHOOK_SECRET` |
| **Sentry** | Settings → Developer Settings → Internal Integration (webhook) | `https://<host>/webhooks/sentry` | `SENTRY_WEBHOOK_SECRET` |

Register the slash commands you want in the Slack app (e.g. `/standup`, `/bug`,
`/pr`), all pointing at `/slack/command`.

> **Signature verification** is skipped while a provider's secret is unset (dev
> mode). Set all three secrets in production — see the Security section of the
> [root README](../README.md#security).

## 6. App configuration (`.env`)

| Var | Purpose |
|-----|---------|
| `ANTHROPIC_API_KEY`, `CLAUDE_MODEL` | LLM for classification + summaries |
| `CORAL_COMMAND`, `CORAL_ARGS`, `CORAL_CWD` | How to launch `coral mcp-stdio` |
| `SLACK_BOT_TOKEN`, `SLACK_DEFAULT_CHANNEL`, `ENGINEERING_CHANNEL` | Slack delivery |
| `SLACK_SIGNING_SECRET`, `GITHUB_WEBHOOK_SECRET`, `SENTRY_WEBHOOK_SECRET` | Request verification |
| `GITHUB_OWNER`, `GITHUB_REPO`, `SENTRY_PROJECT` | Which repo/project agents query |
| `IDENTITY_MAP` | Slack→Jira/GitHub identity map (JSON) for per-user scoping |

## 7. Smoke test

```bash
curl https://<host>/health         # -> {"status":"ok"}
```

Then trigger `/standup` in Slack and open a test PR to confirm the GitHub
webhook path. Watch the service logs for the background graph run.
```
