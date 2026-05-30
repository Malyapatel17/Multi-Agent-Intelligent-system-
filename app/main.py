"""FastAPI entry points for the multi-agent dev intelligence system.

All inbound requests (GitHub/Sentry webhooks, Slack slash commands) are parsed
into an initial GraphState and handed to the runtime, which runs the agent
graph and posts the result to Slack. Webhook/command handlers return 200
immediately and run the (potentially slow) agent work as a background task so
Slack and the webhook senders don't time out.
"""
from __future__ import annotations

from fastapi import BackgroundTasks, FastAPI, Form, Request

from app.ingest import (
    parse_github_webhook,
    parse_sentry_webhook,
    parse_slash_command,
)


def create_app(runtime=None) -> FastAPI:
    """Build the FastAPI app. ``runtime`` is injectable for testing; in
    production it is constructed lazily from config on first use."""
    app = FastAPI(title="Dev Intelligence Agents")
    app.state.runtime = runtime

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
        payload = await request.json()
        state = parse_github_webhook(payload)
        background.add_task(_runtime().handle, state)
        return {"accepted": True}

    @app.post("/webhooks/sentry")
    async def sentry_webhook(request: Request, background: BackgroundTasks):
        payload = await request.json()
        state = parse_sentry_webhook(payload)
        background.add_task(_runtime().handle, state)
        return {"accepted": True}

    @app.post("/slack/command")
    async def slack_command(
        background: BackgroundTasks,
        command: str = Form(""),
        text: str = Form(""),
        user_id: str = Form(""),
        channel_id: str = Form(""),
    ):
        state = parse_slash_command(
            {
                "command": command,
                "text": text,
                "user_id": user_id,
                "channel_id": channel_id,
            }
        )
        background.add_task(_runtime().handle, state)
        # Immediate Slack ack; the real answer is posted to the channel async.
        return {"response_type": "ephemeral", "text": "On it — gathering your dev intel…"}

    return app


# Module-level app for `uvicorn app.main:app`.
app = create_app()
