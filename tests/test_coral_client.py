"""Tests for the Coral SQL tool layer."""
import pytest

from app.coral import (
    CoralClient,
    CoralError,
    _rows_from_result,
    _coerce_rows,
)


class FakeText:
    """Mimics an MCP TextContent block."""

    def __init__(self, text):
        self.text = text


class FakeToolResult:
    """Mimics an MCP CallToolResult."""

    def __init__(self, content=None, structuredContent=None, isError=False):
        self.content = content or []
        self.structuredContent = structuredContent
        self.isError = isError


class FakeTransport:
    """Records the query it was called with and returns a canned response."""

    def __init__(self, response=None, raise_exc=None):
        self.response = response if response is not None else {"rows": []}
        self.raise_exc = raise_exc
        self.calls = []

    async def query(self, sql: str) -> dict:
        self.calls.append(sql)
        if self.raise_exc:
            raise self.raise_exc
        return self.response


async def test_sql_returns_rows_from_transport():
    transport = FakeTransport(
        response={"rows": [{"id": 1, "title": "Fix login"}]}
    )
    client = CoralClient(transport=transport)

    rows = await client.sql("SELECT * FROM jira.issues")

    assert rows == [{"id": 1, "title": "Fix login"}]
    assert transport.calls == ["SELECT * FROM jira.issues"]


async def test_sql_returns_empty_list_when_no_rows():
    client = CoralClient(transport=FakeTransport(response={"rows": []}))

    rows = await client.sql("SELECT * FROM github.pulls WHERE 1=0")

    assert rows == []


async def test_sql_wraps_transport_errors_in_coral_error():
    transport = FakeTransport(raise_exc=RuntimeError("connection refused"))
    client = CoralClient(transport=transport)

    with pytest.raises(CoralError) as exc_info:
        await client.sql("SELECT 1")

    assert "connection refused" in str(exc_info.value)


# --- MCP result parsing (Coral `sql` tool returns `coral sql --format json`) ---

def test_rows_from_result_parses_json_array_text():
    result = FakeToolResult(content=[FakeText('[{"key": "ENG-1"}]')])
    assert _rows_from_result(result) == [{"key": "ENG-1"}]


def test_rows_from_result_prefers_structured_content():
    result = FakeToolResult(
        content=[FakeText("ignored")],
        structuredContent=[{"key": "ENG-2"}],
    )
    assert _rows_from_result(result) == [{"key": "ENG-2"}]


def test_rows_from_result_empty_text_is_empty_list():
    assert _rows_from_result(FakeToolResult(content=[FakeText("")])) == []


def test_rows_from_result_raises_on_non_json():
    result = FakeToolResult(content=[FakeText("not json at all")])
    with pytest.raises(CoralError):
        _rows_from_result(result)


def test_coerce_rows_unwraps_rows_key():
    assert _coerce_rows({"rows": [{"a": 1}]}) == [{"a": 1}]
    assert _coerce_rows([{"a": 1}]) == [{"a": 1}]
    assert _coerce_rows({"unexpected": 1}) is None
