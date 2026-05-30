"""Coral SQL tool layer.

Coral exposes any API, database, or file as queryable SQL. Every agent in this
system reads external data exclusively through ``CoralClient.sql`` — no agent
talks to Jira, GitHub, or Sentry directly.

The actual MCP transport is injected so the client is fully testable without a
live Coral server. ``HttpCoralTransport`` is the production transport; tests
pass a fake.
"""
from __future__ import annotations

from typing import Any, Protocol

import httpx

from app.config import get_settings


class CoralError(Exception):
    """Raised when a Coral query fails (transport error, bad SQL, etc.)."""


class CoralTransport(Protocol):
    """Anything that can execute a SQL string against Coral and return a dict
    containing a ``rows`` key."""

    async def query(self, sql: str) -> dict[str, Any]:
        ...


class HttpCoralTransport:
    """Production transport that posts SQL to the Coral MCP HTTP endpoint."""

    def __init__(self, base_url: str | None = None, api_key: str | None = None):
        settings = get_settings()
        self.base_url = (base_url or settings.coral_mcp_url).rstrip("/")
        self.api_key = api_key if api_key is not None else settings.coral_api_key

    async def query(self, sql: str) -> dict[str, Any]:
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(
                f"{self.base_url}/sql",
                json={"query": sql},
                headers=headers,
            )
            resp.raise_for_status()
            return resp.json()


class CoralClient:
    """High-level Coral query interface used by agents."""

    def __init__(self, transport: CoralTransport | None = None):
        self._transport = transport or HttpCoralTransport()

    async def sql(self, query: str) -> list[dict[str, Any]]:
        """Run a SQL query through Coral and return the result rows.

        Raises ``CoralError`` on any transport or execution failure.
        """
        try:
            result = await self._transport.query(query)
        except CoralError:
            raise
        except Exception as exc:  # noqa: BLE001 - intentional wrap
            raise CoralError(f"Coral query failed: {exc}") from exc
        return result.get("rows", [])
