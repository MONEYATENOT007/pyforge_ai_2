"""Pure, offline session export and import validation."""

from datetime import datetime, timezone
import json
import re
from uuid import UUID

EXPORT_SCHEMA = "1.0"

_REDACTIONS = (
    (re.compile(r"(?i)\b(?:sk-[A-Za-z0-9_-]{16,}|ghp_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,})\b"), "[REDACTED SECRET]"),
    (re.compile(r"(?im)(\b(?:api[_-]?key|access[_-]?token|password|secret)\b[\"']?\s*[:=]\s*[\"']?)[^\s,\"'}]+"), r"\1[REDACTED SECRET]"),
    (re.compile(r"(?i)(\bBearer\s+)[A-Za-z0-9._~-]+"), r"\1[REDACTED SECRET]"),
    (re.compile(r"(?i)[\"'][A-Za-z]:\\[^\"']+[\"']"), "[REDACTED PATH]"),
    (re.compile(r"(?i)\b[A-Za-z]:\\(?:[^\\\s<>\"|]+\\)*[^\\\s<>\"|]+"), "[REDACTED PATH]"),
    (re.compile(r"(?i)(?<!\w)/(?:home|Users|mnt|media)/[^\s<>\"']+"), "[REDACTED PATH]"),
)


def redact_text(value: str) -> str:
    for pattern, replacement in _REDACTIONS:
        value = pattern.sub(replacement, value)
    return value


def _safe(value, redact: bool):
    return redact_text(value) if redact and isinstance(value, str) else value


def build_export(session: dict, messages: list[dict], *, redact: bool = True,
                 include_details: bool = True) -> dict:
    last_assistant = next((m for m in reversed(messages) if m["role"] == "assistant"), None)
    last_run = (last_assistant or {}).get("run") or {}
    model = {
        "name": (last_assistant or {}).get("model") or "unknown",
        "digest": last_run.get("model_digest") or "unknown",
        "quantization": last_run.get("quantization") or "unknown",
        "context_tokens": last_run.get("context_tokens", "unknown"),
        "temperature": last_run.get("temperature", "unknown"),
        "top_p": last_run.get("top_p", "unknown"),
        "seed": last_run.get("seed", "unknown"),
        "backend": last_run.get("backend") or "unknown",
    }
    result = {
        "schema_version": EXPORT_SCHEMA,
        "project": "PyForge AI",
        "exported_at": datetime.now(timezone.utc).isoformat(),
        "redacted": redact,
        "session": {
            "id": session["public_id"],
            "title": _safe(session["title"], redact),
            "created_at": session["created_at"],
            "updated_at": session["updated_at"],
        },
        "model": model if include_details else None,
        "messages": [],
    }
    for m in messages:
        item = {
            "id": m["public_id"],
            "role": m["role"],
            "content": _safe(m["content"], redact),
            "timestamp": m["created_at"],
        }
        if include_details:
            run = m.get("run")
            if run:
                run = {key: _safe(value, redact) for key, value in run.items()}
            item["metadata"] = {
                "model": m.get("model") or "unknown",
                "profile": m.get("profile") or "unknown",
                "metrics": m.get("metrics") or {},
                "run": run or {},
            }
            if m["role"] == "assistant" and m.get("rating") in (-1, 1):
                item["feedback"] = {
                    "rating": "up" if m["rating"] == 1 else "down",
                    "comment": _safe(m.get("comment") or "", redact),
                    "candidate": bool(m.get("candidate")),
                    "failure_category": m.get("failure_category") or "",
                    "timestamp": m["feedback_updated_at"],
                    "message_id": m["public_id"],
                }
        result["messages"].append(item)
    return result


def to_markdown(payload: dict) -> str:
    session = payload["session"]
    lines = [
        f"# {session['title']}",
        "",
        f"Session ID: {session['id']}",
        f"Exported at: {payload['exported_at']}",
        f"Redacted: {payload['redacted']}",
    ]
    if payload.get("model"):
        lines += ["", "## Model and configuration", "", "```json",
                  json.dumps(payload["model"], ensure_ascii=False, indent=2), "```"]
    for index, message in enumerate(payload["messages"], 1):
        lines += ["", f"## {index}. {message['role'].capitalize()} — {message['timestamp']}",
                  "", f"Message ID: {message['id']}", ""]
        lines.append(message["content"])
        if message.get("metadata"):
            lines += ["", "<details><summary>Run metadata</summary>", "", "```json",
                      json.dumps(message["metadata"], ensure_ascii=False, indent=2), "```",
                      "", "</details>"]
        if message.get("feedback"):
            feedback = message["feedback"]
            lines += ["", f"Feedback: {feedback['rating']} at {feedback['timestamp']}",
                      f"Category: {feedback['failure_category'] or 'none'}",
                      f"Comment: {feedback['comment']}"]
    return "\n".join(lines) + "\n"


def parse_export(source: str) -> dict:
    """Validate the JSON exchange format without evaluating any message content."""
    try:
        payload = json.loads(source)
    except (ValueError, TypeError) as exc:
        raise ValueError("invalid JSON export") from exc
    if not isinstance(payload, dict) or payload.get("schema_version") != EXPORT_SCHEMA:
        raise ValueError("unsupported session export schema")
    session = payload.get("session")
    messages = payload.get("messages")
    if not isinstance(session, dict) or not isinstance(messages, list):
        raise ValueError("session and messages are required")
    seen = set()
    def check_uuid(value):
        if not isinstance(value, str):
            raise ValueError("UUID must be a string")
        try:
            UUID(value)
        except ValueError as exc:
            raise ValueError("invalid UUID") from exc
        if value in seen:
            raise ValueError("duplicate UUID")
        seen.add(value)
    def check_time(value):
        try:
            datetime.fromisoformat(value)
        except (TypeError, ValueError) as exc:
            raise ValueError("invalid timestamp") from exc
    check_uuid(session.get("id"))
    if not isinstance(session.get("title"), str):
        raise ValueError("session title is required")
    check_time(session.get("created_at"))
    check_time(session.get("updated_at"))
    for m in messages:
        if not isinstance(m, dict):
            raise ValueError("invalid message")
        check_uuid(m.get("id"))
        if m.get("role") not in {"user", "assistant"} or not isinstance(m.get("content"), str):
            raise ValueError("invalid message role or content")
        check_time(m.get("timestamp"))
        feedback = m.get("feedback")
        if feedback:
            if m["role"] != "assistant" or feedback.get("rating") not in {"up", "down"}:
                raise ValueError("invalid feedback")
            if feedback.get("message_id") != m["id"]:
                raise ValueError("feedback message ID mismatch")
            check_time(feedback.get("timestamp"))
    return payload
