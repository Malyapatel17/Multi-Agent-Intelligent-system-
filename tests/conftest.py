"""Shared test fakes for Coral and the LLM."""
import pytest


class FakeCoral:
    """Returns canned rows per query; records queries it received."""

    def __init__(self, rows=None, rows_sequence=None, raise_exc=None):
        self._rows = rows if rows is not None else []
        self._sequence = list(rows_sequence) if rows_sequence else None
        self.raise_exc = raise_exc
        self.queries = []

    async def sql(self, query: str):
        self.queries.append(query)
        if self.raise_exc:
            raise self.raise_exc
        if self._sequence is not None:
            return self._sequence.pop(0)
        return self._rows


class FakeLLM:
    """Returns a fixed string; records the prompts it received."""

    def __init__(self, response="SUMMARY"):
        self.response = response
        self.calls = []

    async def complete(self, system: str, user: str) -> str:
        self.calls.append({"system": system, "user": user})
        return self.response


@pytest.fixture
def fake_llm():
    return FakeLLM()
