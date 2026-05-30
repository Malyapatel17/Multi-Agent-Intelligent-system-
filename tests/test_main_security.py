"""Signature enforcement at the FastAPI endpoint layer."""
import hashlib
import hmac
import json
import time
from urllib.parse import urlencode

import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app


class FakeRuntime:
    def __init__(self):
        self.handled = []

    async def handle(self, state: dict) -> None:
        self.handled.append(state)


@pytest.fixture
def runtime():
    return FakeRuntime()


def _client(runtime, **secret_overrides):
    settings = Settings(**secret_overrides)
    return TestClient(create_app(runtime=runtime, settings=settings))


# --- GitHub ---

def test_github_rejects_bad_signature_when_secret_set(runtime):
    client = _client(runtime, github_webhook_secret="ghsecret")

    resp = client.post(
        "/webhooks/github",
        json={"action": "opened", "pull_request": {"number": 1}},
        headers={"X-Hub-Signature-256": "sha256=bad"},
    )

    assert resp.status_code == 401
    assert runtime.handled == []


def test_github_accepts_valid_signature(runtime):
    client = _client(runtime, github_webhook_secret="ghsecret")
    body = json.dumps({"action": "opened", "pull_request": {"number": 1}}).encode()
    sig = "sha256=" + hmac.new(b"ghsecret", body, hashlib.sha256).hexdigest()

    resp = client.post(
        "/webhooks/github",
        content=body,
        headers={"X-Hub-Signature-256": sig, "Content-Type": "application/json"},
    )

    assert resp.status_code == 200
    assert runtime.handled[0]["event_type"] == "pr_opened"


# --- Slack ---

def test_slack_rejects_bad_signature_when_secret_set(runtime):
    client = _client(runtime, slack_signing_secret="shhh")

    resp = client.post(
        "/slack/command",
        data={"command": "/standup", "user_id": "U1", "channel_id": "C1"},
        headers={"X-Slack-Request-Timestamp": str(int(time.time())),
                 "X-Slack-Signature": "v0=bad"},
    )

    assert resp.status_code == 401
    assert runtime.handled == []


def test_slack_accepts_valid_signature(runtime):
    client = _client(runtime, slack_signing_secret="shhh")
    ts = str(int(time.time()))
    body = urlencode({"command": "/standup", "user_id": "U1", "channel_id": "C1"})
    base = f"v0:{ts}:{body}".encode()
    sig = "v0=" + hmac.new(b"shhh", base, hashlib.sha256).hexdigest()

    resp = client.post(
        "/slack/command",
        content=body,
        headers={
            "X-Slack-Request-Timestamp": ts,
            "X-Slack-Signature": sig,
            "Content-Type": "application/x-www-form-urlencoded",
        },
    )

    assert resp.status_code == 200
    assert runtime.handled[0]["event_type"] == "standup"
