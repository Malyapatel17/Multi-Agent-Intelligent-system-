"""Tests for the Claude LLM wrapper."""
from app.llm import AnthropicLLM


class FakeMessage:
    def __init__(self, text):
        self.content = [type("Block", (), {"type": "text", "text": text})()]


class FakeMessages:
    def __init__(self, text):
        self._text = text
        self.calls = []

    async def create(self, **kwargs):
        self.calls.append(kwargs)
        return FakeMessage(self._text)


class FakeAnthropic:
    def __init__(self, text):
        self.messages = FakeMessages(text)


async def test_complete_returns_text_from_claude():
    fake = FakeAnthropic("Here is your sprint summary.")
    llm = AnthropicLLM(client=fake, model="claude-sonnet-4-6")

    result = await llm.complete(system="You summarize.", user="3 tickets open")

    assert result == "Here is your sprint summary."


async def test_complete_passes_system_and_user_to_claude():
    fake = FakeAnthropic("ok")
    llm = AnthropicLLM(client=fake, model="claude-sonnet-4-6")

    await llm.complete(system="SYS", user="USR")

    call = fake.messages.calls[0]
    assert call["model"] == "claude-sonnet-4-6"
    assert call["system"] == "SYS"
    assert call["messages"] == [{"role": "user", "content": "USR"}]
