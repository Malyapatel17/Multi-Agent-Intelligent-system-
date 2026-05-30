"""Tests for the Coral SQL tool layer."""
import pytest

from app.coral import CoralClient, CoralError


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
