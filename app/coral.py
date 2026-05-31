"""Coral SQL tool layer.

Coral exposes any API, database, or file as queryable SQL. Every agent in this
system reads external data exclusively through ``CoralClient.sql`` — no agent
talks to Jira, GitHub, or Sentry directly.

Coral ships a built-in **MCP server** that presents the runtime to an agent as a
read-only SQL database. The server speaks JSON-RPC over **stdio** (started with
``coral mcp-stdio``) and exposes a tool named ``sql`` — "Execute read-only SQL
against the Coral database" — whose result mirrors ``coral sql --format json``
(an array of row objects). See
https://withcoral.com/docs/guides/use-coral-over-mcp .

The MCP transport is injected behind the ``CoralTransport`` Protocol so the
client is fully testable without a live Coral server: ``StdioMcpCoralTransport``
is the production transport; tests pass a fake.
"""
from __future__ import annotations

import asyncio
import json
from contextlib import AsyncExitStack
from typing import Any, Protocol

from app.config import get_settings

# The Coral MCP server exposes a single query tool. These names are fixed by the
# Coral MCP server (`coral mcp-stdio`); keep them as constants so they are easy
# to confirm/adjust against `coral list_catalog` at integration time.
SQL_TOOL_NAME = "sql"
SQL_TOOL_ARG = "query"


class CoralError(Exception):
    """Raised when a Coral query fails (transport error, bad SQL, etc.)."""


class CoralTransport(Protocol):
    """Anything that can execute a SQL string against Coral and return a dict
    containing a ``rows`` key."""

    async def query(self, sql: str) -> dict[str, Any]:
        ...


class StdioMcpCoralTransport:
    """Production transport: an MCP stdio client that drives ``coral mcp-stdio``.

    Spawning the Coral subprocess and loading source specs is expensive, so the
    session is created lazily on first use and reused for the lifetime of the
    process (guarded by a lock for concurrent webhook/command handling).
    """

    def __init__(
        self,
        command: str | None = None,
        args: list[str] | None = None,
        cwd: str | None = None,
    ):
        settings = get_settings()
        self._command = command or settings.coral_command
        self._args = args if args is not None else list(settings.coral_args)
        # Coral loads source specs relative to its working directory; default to
        # the configured project root (where `coral/sources/*.yaml` live).
        self._cwd = cwd if cwd is not None else (settings.coral_cwd or None)
        self._stack: AsyncExitStack | None = None
        self._session: Any = None
        self._lock = asyncio.Lock()

    async def _ensure_session(self) -> Any:
        if self._session is not None:
            return self._session
        async with self._lock:
            if self._session is not None:  # set while we waited for the lock
                return self._session
            try:
                from mcp import ClientSession, StdioServerParameters
                from mcp.client.stdio import stdio_client
            except ImportError as exc:  # pragma: no cover - import guard
                raise CoralError(
                    "The 'mcp' package is required for the Coral stdio transport. "
                    "Install it with `pip install mcp`."
                ) from exc

            stack = AsyncExitStack()
            params = StdioServerParameters(
                command=self._command, args=self._args, cwd=self._cwd
            )
            read, write = await stack.enter_async_context(stdio_client(params))
            session = await stack.enter_async_context(ClientSession(read, write))
            await session.initialize()
            self._stack = stack
            self._session = session
            return session

    async def query(self, sql: str) -> dict[str, Any]:
        session = await self._ensure_session()
        result = await session.call_tool(SQL_TOOL_NAME, {SQL_TOOL_ARG: sql})
        if getattr(result, "isError", False):
            raise CoralError(f"Coral rejected query: {_result_text(result)}")
        return {"rows": _rows_from_result(result)}

    async def aclose(self) -> None:
        """Tear down the MCP session and the Coral subprocess."""
        if self._stack is not None:
            await self._stack.aclose()
            self._stack = None
            self._session = None


def _result_text(result: Any) -> str:
    """Concatenate the text content blocks of an MCP tool result."""
    parts = []
    for block in getattr(result, "content", None) or []:
        text = getattr(block, "text", None)
        if text is not None:
            parts.append(text)
    return "\n".join(parts)


def _rows_from_result(result: Any) -> list[dict[str, Any]]:
    """Extract row dicts from an MCP ``sql`` tool result.

    Coral returns the same payload as ``coral sql --format json`` — an array of
    row objects. Newer MCP servers also surface this as ``structuredContent``;
    prefer that and fall back to parsing the text content block.
    """
    structured = getattr(result, "structuredContent", None)
    rows = _coerce_rows(structured)
    if rows is not None:
        return rows

    text = _result_text(result).strip()
    if not text:
        return []
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError as exc:
        raise CoralError(f"Coral returned non-JSON result: {text[:200]}") from exc
    rows = _coerce_rows(parsed)
    return rows if rows is not None else []


def _coerce_rows(payload: Any) -> list[dict[str, Any]] | None:
    """Normalize a Coral payload into a list of row dicts, or None if unusable."""
    if isinstance(payload, list):
        return payload
    if isinstance(payload, dict):
        for key in ("rows", "result", "data"):
            value = payload.get(key)
            if isinstance(value, list):
                return value
    return None


class CoralClient:
    """High-level Coral query interface used by agents."""

    def __init__(self, transport: CoralTransport | None = None):
        self._transport = transport or StdioMcpCoralTransport()

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
