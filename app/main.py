"""FastAPI entry points for the multi-agent dev intelligence system.

All inbound requests (GitHub/Sentry webhooks, Slack slash commands) are:

1. Read as raw bytes,
2. Verified against the provider's signature (skipped if the corresponding
   secret is not configured — dev mode),
3. Parsed into an initial GraphState,
4. Handed to the runtime as a background task (so Slack / webhook senders get
   an immediate 200 and don't time out).
"""
from __future__ import annotations

import json
from urllib.parse import parse_qs

from fastapi import BackgroundTasks, FastAPI, HTTPException, Request

from app.config import Settings, get_settings
from app.ingest import (
    parse_github_webhook,
    parse_sentry_webhook,
    parse_slash_command,
)
from app.security import (
    verify_github_signature,
    verify_sentry_signature,
    verify_slack_signature,
)


def create_app(runtime=None, settings: Settings | None = None) -> FastAPI:
    """Build the FastAPI app. ``runtime`` and ``settings`` are injectable for
    testing; in production the runtime is built lazily from config."""
    app = FastAPI(title="Dev Intelligence Agents")
    app.state.runtime = runtime
    cfg = settings or get_settings()

    def _runtime():
        if app.state.runtime is None:
            from app.runtime import build_runtime

            app.state.runtime = build_runtime()
        return app.state.runtime

    @app.get("/health")
    async def health():
        return {"status": "ok"}

    @app.post("/webhooks/github")
    async def github_webhook(request: Request, background: BackgroundTasks):
        body = await request.body()
        if cfg.github_webhook_secret and not verify_github_signature(
            cfg.github_webhook_secret,
            body,
            request.headers.get("X-Hub-Signature-256", ""),
        ):
            raise HTTPException(status_code=401, detail="invalid signature")

        state = parse_github_webhook(json.loads(body or b"{}"))
        background.add_task(_runtime().handle, state)
        return {"accepted": True}

    @app.post("/webhooks/sentry")
    async def sentry_webhook(request: Request, background: BackgroundTasks):
        body = await request.body()
        if cfg.sentry_webhook_secret and not verify_sentry_signature(
            cfg.sentry_webhook_secret,
            body,
            request.headers.get("Sentry-Hook-Signature", ""),
        ):
            raise HTTPException(status_code=401, detail="invalid signature")

        state = parse_sentry_webhook(json.loads(body or b"{}"))
        background.add_task(_runtime().handle, state)
        return {"accepted": True}

    @app.post("/slack/command")
    async def slack_command(request: Request, background: BackgroundTasks):
        body = await request.body()
        if cfg.slack_signing_secret and not verify_slack_signature(
            cfg.slack_signing_secret,
            request.headers.get("X-Slack-Request-Timestamp", ""),
            body.decode(),
            request.headers.get("X-Slack-Signature", ""),
        ):
            raise HTTPException(status_code=401, detail="invalid signature")

        form = {k: v[0] for k, v in parse_qs(body.decode()).items()}
        state = parse_slash_command(form)
        background.add_task(_runtime().handle, state)
        # Immediate Slack ack; the real answer is posted to the channel async.
        return {"response_type": "ephemeral", "text": "On it — gathering your dev intel…"}

    return app


# Module-level app for `uvicorn app.main:app`.
app = create_app()
