"""Snapshot redacted Session 02 examples for static regression tests.

Run with the project environment. This reads the chat database and never imports
or executes code from a model response. It refuses to replace an existing fixture.
"""

import json
from pathlib import Path

from pyforge.chat.store import ChatStore

SESSION_PREFIX = "e9a09316"
CASE_IDS = {
    "renamer_initial": "01828d26",
    "renamer_revision": "1210733c",
    "dashboard_initial": "53d49422",
    "dashboard_revision": "f2133426",
    "dashboard_repair": "98901384",
}


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    store = ChatStore(root / "local_runtime" / "data" / "chat.sqlite3")
    session = next(row for row in store.list_sessions() if row["public_id"].startswith(SESSION_PREFIX))
    payload = json.loads(store.export_json(session["id"], redact=True))
    prompts: list[str] = []
    cases = []
    for message in payload["messages"]:
        if message["role"] == "user":
            prompts.append(message["content"])
            continue
        case_name = next((name for name, prefix in CASE_IDS.items() if message["id"].startswith(prefix)), None)
        if case_name:
            cases.append({
                "case_id": case_name,
                "source_message_id": message["id"],
                "prompt": prompts[-1],
                "context": prompts[:-1],
                "response": message["content"],
            })
    if len(cases) != len(CASE_IDS):
        raise RuntimeError("Session 02 is missing one or more expected responses")
    output = root / "tests" / "fixtures" / "session02_cases.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("x", encoding="utf-8") as stream:
        json.dump({
            "fixture_version": "session02-static-1",
            "source_session_id": session["public_id"],
            "redacted": True,
            "cases": cases,
        }, stream, ensure_ascii=False, indent=2)
        stream.write("\n")
    print(f"Saved {len(cases)} redacted, non-executed cases to {output}")


if __name__ == "__main__":
    main()
