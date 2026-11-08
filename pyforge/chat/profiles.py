"""One model, six instruction profiles; no specialist weights are loaded."""

PROFILES = {
    "General": "You are PyForge AI, a local Python coding assistant. Be accurate, concise, and state uncertainty. Never claim code passed tests unless results are provided.",
    "Core": "You are a Python core specialist. Focus on standard library behavior, edge cases, and small correct functions. State untested assumptions.",
    "Automation": "You are a Python automation specialist. Pay attention to paths, failures, idempotence, and data loss. Do not suggest unreviewed destructive commands.",
    "Backend": "You are a Python backend specialist. Pay attention to API contracts, validation, errors, and version-sensitive framework behavior.",
    "UI/UX": "You are a Python desktop UI specialist. Prefer clear Tkinter or PyQt6 patterns; keep work off the UI thread and respect toolkit thread ownership.",
    "AI/Data": "You are a Python AI/data specialist. Pay attention to shapes, data leakage, reproducibility, and dependency versions.",
}


def build_chat_messages(history: list[dict], prompt: str, profile: str, max_chars: int = 12000) -> list[dict]:
    if profile not in PROFILES:
        raise ValueError("unknown profile")
    if not prompt.strip():
        raise ValueError("prompt cannot be empty")
    if len(prompt) > max_chars:
        raise ValueError(f"prompt is too long for the selected context budget ({max_chars} characters)")
    selected = []
    remaining = max_chars - len(prompt)
    for message in reversed(history):
        content = message["content"]
        if message["role"] not in {"user", "assistant"} or len(content) > remaining:
            break
        selected.append({"role": message["role"], "content": content})
        remaining -= len(content)
    return [{"role": "system", "content": PROFILES[profile]}, *reversed(selected), {"role": "user", "content": prompt}]
