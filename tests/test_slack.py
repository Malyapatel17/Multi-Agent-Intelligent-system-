"""Tests for the Slack delivery notifier."""
from app.slack import SlackNotifier


class FakeSlackClient:
    def __init__(self):
        self.calls = []

    async def chat_postMessage(self, **kwargs):
        self.calls.append(kwargs)
        return {"ok": True}


async def test_post_sends_message_to_channel():
    client = FakeSlackClient()
    notifier = SlackNotifier(client=client, default_channel="#dev-intel")

    await notifier.post("Hello team", channel="#eng")

    assert client.calls[0]["channel"] == "#eng"
    assert client.calls[0]["text"] == "Hello team"


async def test_post_uses_default_channel_when_none_given():
    client = FakeSlackClient()
    notifier = SlackNotifier(client=client, default_channel="#dev-intel")

    await notifier.post("hi", channel="")

    assert client.calls[0]["channel"] == "#dev-intel"
