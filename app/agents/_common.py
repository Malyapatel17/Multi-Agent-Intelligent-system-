"""Shared helpers for agent nodes."""
from __future__ import annotations

import json
from typing import Any


def format_rows(rows: list[dict[str, Any]]) -> str:
    """Render Coral result rows as compact JSON for the LLM prompt."""
    if not rows:
        return "(no rows returned)"
    return json.dumps(rows, indent=2, default=str)


def error_update(context_key: str, agent_label: str, exc: Exception) -> dict:
    """Standard non-fatal failure update: blank context + recorded error."""
    return {context_key: "", "errors": [f"{agent_label}: {exc}"]}
