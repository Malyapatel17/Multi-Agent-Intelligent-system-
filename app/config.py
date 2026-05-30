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

    # Coral MCP
    coral_mcp_url: str = "http://localhost:8765"
    coral_api_key: str = ""

    # Slack
    slack_bot_token: str = ""
    slack_signing_secret: str = ""
    slack_default_channel: str = "#dev-intel"
    engineering_channel: str = "#engineering"

    # Webhook secrets
    github_webhook_secret: str = ""
    sentry_webhook_secret: str = ""


_settings: Settings | None = None


def get_settings() -> Settings:
    """Return a cached Settings instance."""
    global _settings
    if _settings is None:
        _settings = Settings()
    return _settings
