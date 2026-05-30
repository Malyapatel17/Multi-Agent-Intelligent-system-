"""Slack delivery layer.

Posts the formatted ``final_message`` to a Slack channel or DM. The underlying
Slack client is injectable so delivery is testable without a real token.
"""
from __future__ import annotations

from typing import Any

from app.config import get_settings


class SlackNotifier:
    def __init__(self, client: Any | None = None, default_channel: str | None = None):
        settings = get_settings()
        self.default_channel = default_channel or settings.slack_default_channel
        if client is not None:
            self._client = client
        else:
            from slack_sdk.web.async_client import AsyncWebClient

            self._client = AsyncWebClient(token=settings.slack_bot_token)

    async def post(self, text: str, channel: str = "") -> None:
        await self._client.chat_postMessage(
            channel=channel or self.default_channel,
            text=text,
        )
