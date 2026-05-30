"""Integration tests for the FastAPI entry points."""
import pytest
from fastapi.testclient import TestClient

from app.main import create_app


class FakeRuntime:
    """Captures the states handed to it by the endpoints."""

    def __init__(self):
        self.handled = []

    async def handle(self, state: dict) -> None:
        self.handled.append(state)


@pytest.fixture
def runtime():
    return FakeRuntime()


@pytest.fixture
def client(runtime):
    return TestClient(create_app(runtime=runtime))


def test_health_endpoint(client):
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


def test_github_webhook_dispatches_pr_opened(client, runtime):
    resp = client.post(
        "/webhooks/github",
        json={"action": "opened", "pull_request": {"number": 42}},
    )
    assert resp.status_code == 200
    assert runtime.handled[0]["event_type"] == "pr_opened"
    assert runtime.handled[0]["raw_payload"]["pr_number"] == 42


def test_sentry_webhook_dispatches_error(client, runtime):
    resp = client.post(
        "/webhooks/sentry",
        json={"data": {"error": {"id": "E-1"}}},
    )
    assert resp.status_code == 200
    assert runtime.handled[0]["event_type"] == "sentry_error"


def test_slack_command_dispatches_standup(client, runtime):
    resp = client.post(
        "/slack/command",
        data={"command": "/standup", "text": "", "user_id": "U1", "channel_id": "C1"},
    )
    assert resp.status_code == 200
    assert runtime.handled[0]["event_type"] == "standup"
    assert runtime.handled[0]["user_id"] == "U1"
