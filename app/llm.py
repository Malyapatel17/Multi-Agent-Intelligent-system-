"""Claude LLM wrapper used by all agents.

A thin async interface over the Anthropic SDK. The underlying client is
injectable so agents can be tested without network access or API keys.
"""
from __future__ import annotations

from typing import Any, Protocol

from app.config import get_settings

# Conservative default; agents synthesize short summaries.
DEFAULT_MAX_TOKENS = 1024


class LLM(Protocol):
    """Minimal completion interface agents depend on."""

    async def complete(self, system: str, user: str) -> str:
        ...


class AnthropicLLM:
    """Production LLM backed by the Anthropic async client."""

    def __init__(
        self,
        client: Any | None = None,
        model: str | None = None,
        max_tokens: int = DEFAULT_MAX_TOKENS,
    ):
        settings = get_settings()
        self.model = model or settings.claude_model
        self.max_tokens = max_tokens
        if client is not None:
            self._client = client
        else:
            # Imported lazily so the package imports without a key present.
            from anthropic import AsyncAnthropic

            self._client = AsyncAnthropic(api_key=settings.anthropic_api_key)

    async def complete(self, system: str, user: str) -> str:
        message = await self._client.messages.create(
            model=self.model,
            max_tokens=self.max_tokens,
            system=system,
            messages=[{"role": "user", "content": user}],
        )
        return _extract_text(message)


def _extract_text(message: Any) -> str:
    """Join all text blocks from an Anthropic message response."""
    parts = [
        block.text
        for block in getattr(message, "content", [])
        if getattr(block, "type", None) == "text"
    ]
    return "".join(parts)
