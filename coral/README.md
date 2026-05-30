# Coral Source Specs

This directory holds the [Coral](https://github.com/withcoral/coral) source
specs that expose the system's external data as SQL. The agents query these
tables through Coral — they never call Jira/GitHub/Sentry APIs directly.

> **Where credentials live:** source credentials (e.g. your Jira API token) are
> configured in **Coral's** environment, not this app's `.env`. The app only
> needs `CORAL_MCP_URL` / `CORAL_API_KEY` to reach Coral.

## `sources/jira.yaml` — Jira Cloud

Exposes the `jira.issues` table, which powers
[`app/agents/jira_agent.py`](../app/agents/jira_agent.py).

| Item | Value |
|------|-------|
| Backend | HTTP — `GET /rest/api/3/search/jql` (Jira Cloud REST v3) |
| Auth | Basic (account email + API token) |
| Required filter | `jql` (provider JQL string) |
| Pagination | Cursor (`nextPageToken`) |
| Key columns | `key`, `summary`, `status_name`, `assignee_display_name`, `priority_name`, `created`, `updated` |

### Configure & load

```sh
# 1. Provide credentials as environment variables (names match the spec inputs)
export JIRA_BASE_URL="https://<your-site>.atlassian.net"
export JIRA_EMAIL="you@example.com"
export JIRA_API_TOKEN="<atlassian-api-token>"   # id.atlassian.com/manage-profile/security/api-tokens

# 2. Lint, load, and smoke-test the source
coral source lint ./coral/sources/jira.yaml
coral source add --file ./coral/sources/jira.yaml
coral source test jira
```

### Inspect & query

```sh
# Confirm the table, columns, and required filters are exposed
coral sql "SELECT table_name, description, required_filters
           FROM coral.tables WHERE schema_name = 'jira'"
coral sql "SELECT column_name, data_type, is_required_filter, is_virtual
           FROM coral.columns WHERE schema_name = 'jira' ORDER BY ordinal_position"

# The exact query the Jira agent runs (active sprint, newest first)
coral sql "SELECT key, summary, status_name, assignee_display_name, updated
           FROM jira.issues
           WHERE jql = 'sprint in openSprints() ORDER BY updated DESC'
           LIMIT 5"
```

Scope the `jql` with a `project` or `created` clause on large instances to
avoid heavy scans, e.g. `... AND project = ENG ORDER BY updated DESC`.

> **Note:** Coral also ships an official, broader `jira` core source. This
> standalone spec is scoped to exactly what the Jira agent needs (issues), so it
> can be loaded with a single `coral source add --file` and reviewed in one place.

## Adding more sources

GitHub and Sentry currently use illustrative SQL in their agents. To make them
live, author `sources/github.yaml` and `sources/sentry.yaml` the same way (both
have official references in the Coral repo under `sources/core/`).
