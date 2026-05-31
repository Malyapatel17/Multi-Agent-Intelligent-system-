"""Application configuration loaded from environment variables.

Credentials are intentionally optional at import time so the code can be
developed and tested before real credentials are provisioned. Validation that
a given credential is present happens at the point of use.
"""
from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Anthropic / Claude
    anthropic_api_key: str = ""
    claude_model: str = "claude-sonnet-4-6"

    # Coral MCP (stdio transport — `coral mcp-stdio`)
    coral_command: str = "coral"
    coral_args: list[str] = ["mcp-stdio"]
    # Working directory Coral runs in; source specs (coral/sources/*.yaml) load
    # relative to it. Empty = inherit this process's cwd.
    coral_cwd: str = ""

    # Slack
    slack_bot_token: str = ""
    slack_signing_secret: str = ""
    slack_default_channel: str = "#dev-intel"
    engineering_channel: str = "#engineering"

    # Webhook secrets
    github_webhook_secret: str = ""
    sentry_webhook_secret: str = ""

    # Default repo / project the agents query (required by GitHub/Sentry APIs).
    github_owner: str = ""
    github_repo: str = ""
    sentry_project: str = ""

    # Slack user ID -> provider identity map (JSON). Lets agents scope queries to
    # the triggering user. See app/identity.py for the shape. Empty = no scoping.
    identity_map: str = ""


_settings: Settings | None = None


def get_settings() -> Settings:
    """Return a cached Settings instance."""
    global _settings
    if _settings is None:
        _settings = Settings()
    return _settings
