# Coral Source Specs

This directory holds the [Coral](https://github.com/withcoral/coral) source
specs that expose the system's external data as SQL. The agents query these
tables through Coral — they never call Jira/GitHub/Sentry APIs directly.

> **Where credentials live:** source credentials (e.g. your Jira API token) are
> configured in **Coral's** environment, not this app's `.env`. The app reaches
> Coral by launching the CLI as an MCP stdio subprocess (`coral mcp-stdio`) and
> calling its `sql` tool — see `CORAL_COMMAND` / `CORAL_ARGS` / `CORAL_CWD` in
> `.env.example` and [`app/coral.py`](../app/coral.py).

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

## `sources/github.yaml` — GitHub

Powers [`pr_agent.py`](../app/agents/pr_agent.py) and the commit-history step of
[`sentry_agent.py`](../app/agents/sentry_agent.py).

| Item | Value |
|------|-------|
| Auth | `Authorization: Bearer <GITHUB_TOKEN>` |
| Tables | `github.pulls`, `github.commits` |
| Required filters | `owner`, `repo` (the API needs them in the path) |
| Pagination | Link header |

```sh
export GITHUB_API_BASE="https://api.github.com"   # or https://<host>/api/v3
export GITHUB_TOKEN="$(gh auth token)"            # or a PAT with repo scope
coral source lint ./coral/sources/github.yaml
coral source add --file ./coral/sources/github.yaml
coral sql "SELECT number, title, state, author_login FROM github.pulls
           WHERE owner='withcoral' AND repo='coral' AND state='open' LIMIT 5"
```

> **No line blame:** GitHub REST has no per-line blame endpoint. The Sentry
> agent instead reads `github.commits WHERE path='<file>'` (newest commit =
> likely owner).

## `sources/sentry.yaml` — Sentry

Powers the error-lookup step of [`sentry_agent.py`](../app/agents/sentry_agent.py).

| Item | Value |
|------|-------|
| Auth | `Authorization: Bearer <SENTRY_TOKEN>` |
| Table | `sentry.issues` |
| Filters | `project`, `query` (Sentry search); filter `WHERE id='<issue_id>'` for one issue |
| Pagination | Link header |

```sh
export SENTRY_ORG="your-org-slug"
export SENTRY_TOKEN="<sentry-auth-token>"   # scopes: org:read, project:read, event:read
coral source lint ./coral/sources/sentry.yaml
coral source add --file ./coral/sources/sentry.yaml
coral sql "SELECT id, title, culprit, metadata_filename FROM sentry.issues
           WHERE project='my-project' LIMIT 5"
```

## Which repo/project the agents query

GitHub and Sentry APIs require an `owner`/`repo`/`project`. The agents read these
from the **app's** config (`GITHUB_OWNER`, `GITHUB_REPO`, `SENTRY_PROJECT` in
`.env`) and inject them into the SQL. The source **credentials** (tokens) live in
Coral's environment; the repo/project selection lives in the app.

> Coral ships broader official `github` and `sentry` core sources too. These
> standalone specs are intentionally scoped to just the tables the agents use.
