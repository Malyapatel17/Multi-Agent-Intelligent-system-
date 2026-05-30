"""Inbound request signature verification.

Each provider signs requests differently:

- **Slack**: ``v0=<hmac>`` over ``v0:{timestamp}:{raw_body}`` plus a 5-minute
  freshness window on the timestamp (replay protection).
- **GitHub**: ``sha256=<hmac>`` over the raw body (``X-Hub-Signature-256``).
- **Sentry**: bare hex ``<hmac>`` over the raw body (``Sentry-Hook-Signature``).

All comparisons use ``hmac.compare_digest`` to avoid timing attacks. These are
pure functions; the FastAPI layer reads the raw body and headers and calls them.
"""
from __future__ import annotations

import hashlib
import hmac
import time

# Reject Slack requests whose timestamp is older than this (seconds).
SLACK_MAX_AGE = 300


def verify_slack_signature(
    signing_secret: str,
    timestamp: str,
    body: str,
    signature: str,
    now: float | None = None,
) -> bool:
    """Verify a Slack request signature with replay protection."""
    try:
        ts = int(timestamp)
    except (TypeError, ValueError):
        return False

    current = time.time() if now is None else now
    if abs(current - ts) > SLACK_MAX_AGE:
        return False

    base = f"v0:{timestamp}:{body}".encode()
    expected = "v0=" + hmac.new(
        signing_secret.encode(), base, hashlib.sha256
    ).hexdigest()
    return hmac.compare_digest(expected, signature or "")


def verify_github_signature(secret: str, body: bytes, signature_header: str) -> bool:
    """Verify a GitHub ``X-Hub-Signature-256`` header."""
    expected = "sha256=" + hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, signature_header or "")


def verify_sentry_signature(secret: str, body: bytes, signature_header: str) -> bool:
    """Verify a Sentry ``Sentry-Hook-Signature`` header (bare hex digest)."""
    expected = hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, signature_header or "")
