"""Slack -> provider identity mapping.

A Slack user ID (e.g. ``U012ABC``) is not a Jira ``accountId`` nor a GitHub
login, so agents cannot scope queries to "the person who triggered this" without
a translation layer. This module is that layer.

For now the map is static, loaded from the ``IDENTITY_MAP`` setting (a JSON
object). A future enhancement would resolve it live (Slack profile email ->
Jira/GitHub user lookup), but the agents only depend on the ``IdentityMap``
interface, so that swap is local to this file.

Expected JSON shape::

    {
      "U012ABC": {"jira": "557058:1a2b...", "github": "octocat"},
      "U345DEF": {"github": "hubot"}
    }
"""
from __future__ import annotations

import json
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.config import Settings


class IdentityMap:
    """Translates a Slack user ID into provider-specific identities."""

    def __init__(
        self,
        slack_to_jira: dict[str, str] | None = None,
        slack_to_github: dict[str, str] | None = None,
    ):
        self._slack_to_jira = slack_to_jira or {}
        self._slack_to_github = slack_to_github or {}

    def jira_account_id(self, slack_user_id: str) -> str | None:
        """Return the Jira accountId for a Slack user, or None if unmapped."""
        if not slack_user_id:
            return None
        return self._slack_to_jira.get(slack_user_id)

    def github_login(self, slack_user_id: str) -> str | None:
        """Return the GitHub login for a Slack user, or None if unmapped."""
        if not slack_user_id:
            return None
        return self._slack_to_github.get(slack_user_id)


def load_identity_map(settings: "Settings | None" = None) -> IdentityMap:
    """Build an :class:`IdentityMap` from the ``IDENTITY_MAP`` JSON setting.

    A malformed or empty value yields an empty (no-op) map rather than raising,
    so a misconfiguration degrades gracefully to "no per-user scoping".
    """
    if settings is None:
        from app.config import get_settings

        settings = get_settings()

    raw = (settings.identity_map or "").strip()
    if not raw:
        return IdentityMap()

    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        return IdentityMap()
    if not isinstance(parsed, dict):
        return IdentityMap()

    slack_to_jira: dict[str, str] = {}
    slack_to_github: dict[str, str] = {}
    for slack_id, providers in parsed.items():
        if not isinstance(providers, dict):
            continue
        if providers.get("jira"):
            slack_to_jira[slack_id] = str(providers["jira"])
        if providers.get("github"):
            slack_to_github[slack_id] = str(providers["github"])

    return IdentityMap(slack_to_jira=slack_to_jira, slack_to_github=slack_to_github)
