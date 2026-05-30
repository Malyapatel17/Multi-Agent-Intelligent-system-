"""Parse inbound payloads (webhooks, Slack commands) into initial GraphState.

These are pure functions so they can be tested without a running server. Each
returns a partial ``GraphState`` dict suitable for ``graph.ainvoke``.
"""
from __future__ import annotations

from app.config import get_settings

# Maps a slash command to its on-demand event type.
_SLASH_EVENTS = {
    "/standup": "standup",
    "/bug": "bug_query",
    "/pr": "pr_query",
}


def parse_github_webhook(payload: dict) -> dict:
    """GitHub webhook -> state. Only 'opened' PRs are actionable today."""
    action = payload.get("action")
    pr = payload.get("pull_request") or {}
    if action == "opened":
        return {
            "trigger_type": "webhook",
            "event_type": "pr_opened",
            "raw_payload": {"pr_number": pr.get("number")},
            "slack_channel": get_settings().engineering_channel,
        }
    return {
        "trigger_type": "webhook",
        "event_type": "unknown",
        "raw_payload": payload,
        "slack_channel": get_settings().engineering_channel,
    }


def parse_sentry_webhook(payload: dict) -> dict:
    """Sentry webhook -> state."""
    error = (payload.get("data") or {}).get("error") or {}
    return {
        "trigger_type": "webhook",
        "event_type": "sentry_error",
        "raw_payload": {"error_id": error.get("id")},
        "slack_channel": get_settings().engineering_channel,
    }


def parse_slash_command(form: dict) -> dict:
    """Slack slash command -> state.

    Known commands map to a fixed event type; unknown commands defer to the
    supervisor's LLM classifier by leaving ``event_type`` unset.
    """
    command = (form.get("command") or "").strip()
    text = (form.get("text") or "").strip()
    state: dict = {
        "trigger_type": "on_demand",
        "user_id": form.get("user_id", ""),
        "slack_channel": form.get("channel_id", ""),
        "user_text": text,
    }

    event_type = _SLASH_EVENTS.get(command)
    if event_type == "bug_query":
        state["event_type"] = "bug_query"
        state["raw_payload"] = {"error_id": text}
    elif event_type == "pr_query":
        state["event_type"] = "pr_query"
        state["raw_payload"] = {"pr_number": int(text) if text.isdigit() else None}
    elif event_type == "standup":
        state["event_type"] = "standup"

    return state
