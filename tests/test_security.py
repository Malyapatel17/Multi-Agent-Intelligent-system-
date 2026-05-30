"""Tests for inbound request signature verification."""
import hashlib
import hmac
import time

from app.security import (
    verify_github_signature,
    verify_sentry_signature,
    verify_slack_signature,
)


# --- Slack ---

def _slack_sig(secret: str, timestamp: str, body: str) -> str:
    base = f"v0:{timestamp}:{body}".encode()
    digest = hmac.new(secret.encode(), base, hashlib.sha256).hexdigest()
    return f"v0={digest}"


def test_slack_signature_accepts_valid():
    secret, body = "shhh", "command=/standup&text="
    ts = str(int(time.time()))
    sig = _slack_sig(secret, ts, body)

    assert verify_slack_signature(secret, ts, body, sig) is True


def test_slack_signature_rejects_tampered_body():
    secret, ts = "shhh", str(int(time.time()))
    sig = _slack_sig(secret, ts, "original")

    assert verify_slack_signature(secret, ts, "tampered", sig) is False


def test_slack_signature_rejects_stale_timestamp():
    secret, body = "shhh", "x"
    old_ts = str(int(time.time()) - 600)  # 10 minutes old
    sig = _slack_sig(secret, old_ts, body)

    assert verify_slack_signature(secret, old_ts, body, sig) is False


# --- GitHub ---

def _github_sig(secret: str, body: bytes) -> str:
    digest = hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
    return f"sha256={digest}"


def test_github_signature_accepts_valid():
    secret, body = "ghsecret", b'{"action":"opened"}'
    sig = _github_sig(secret, body)

    assert verify_github_signature(secret, body, sig) is True


def test_github_signature_rejects_invalid():
    assert verify_github_signature("ghsecret", b"{}", "sha256=deadbeef") is False


# --- Sentry ---

def _sentry_sig(secret: str, body: bytes) -> str:
    return hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()


def test_sentry_signature_accepts_valid():
    secret, body = "sentrysecret", b'{"data":{}}'
    sig = _sentry_sig(secret, body)

    assert verify_sentry_signature(secret, body, sig) is True


def test_sentry_signature_rejects_invalid():
    assert verify_sentry_signature("sentrysecret", b"{}", "nope") is False
