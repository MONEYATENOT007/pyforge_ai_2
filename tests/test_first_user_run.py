import json
from pathlib import Path
import re
import sqlite3
import tempfile
import unittest
from uuid import UUID

from pyforge.chat.export import parse_export
from pyforge.chat.store import ChatStore
from pyforge.evaluation.requirements import review_requirements


REPORT = Path(__file__).resolve().parents[1] / "FIRST_TEST_RUN_BY_USER.md"


def report_case(number: str) -> tuple[str, str]:
    text = REPORT.read_text(encoding="utf-8")
    section = re.search(rf"## [23]\. User Test {number}.*?(?=\n## [34]\.|\Z)", text, re.S)
    if not section:
        raise AssertionError(f"missing user report test {number}")
    prompt = re.search(r"> (.+)", section.group())
    code = re.search(r"```python\s*\n(.*?)\n```", section.group(), re.S)
    if not prompt or not code:
        raise AssertionError(f"incomplete user report test {number}")
    return prompt.group(1), code.group(1)


class FirstUserRunTests(unittest.TestCase):
    def test_export_round_trip_redaction_and_feedback_edit(self):
        with tempfile.TemporaryDirectory() as temp:
            original = ChatStore(Path(temp) / "first.sqlite3")
            session = original.create_session("Unicode Ω")
            prompt = "Use C:\\Users\\alice\\private\\a.py and sk-abcdefghijklmnop1234\nLine two"
            original.add_message(session, "user", prompt)
            content = "Here is code:\n```python\nprint('π')\n```\n" + ("x" * 10001)
            assistant = original.add_message(
                session, "assistant", content, model="local:model", profile="Core",
                run={"backend": "ollama", "context_tokens": 4096, "temperature": 0,
                     "model_digest": "unknown"}, metrics={"status": "complete", "output_tokens": 17},
            )
            original.save_feedback(assistant, -1, "First")
            original.save_feedback(assistant, -1, "No GUI preview", failure_category="Requirement missed")
            payload = json.loads(original.export_json(session, redact=False))
            self.assertEqual(len(payload["messages"]), 2)
            self.assertEqual(payload["messages"][0]["content"], prompt)
            self.assertEqual(payload["messages"][1]["content"], content)
            self.assertEqual(payload["messages"][1]["feedback"]["comment"], "No GUI preview")
            self.assertEqual(payload["messages"][1]["metadata"]["run"]["temperature"], 0)
            self.assertEqual(payload["model"]["quantization"], "unknown")
            UUID(payload["messages"][1]["id"])
            self.assertEqual(parse_export(json.dumps(payload))["session"]["id"], payload["session"]["id"])
            imported = ChatStore(Path(temp) / "second.sqlite3")
            imported_id = imported.import_json(json.dumps(payload))
            self.assertEqual(imported.messages(imported_id)[1]["content"], content)
            self.assertEqual(imported.messages(imported_id)[1]["public_id"], payload["messages"][1]["id"])
            self.assertEqual(imported.messages(imported_id)[1]["feedback_updated_at"],
                             payload["messages"][1]["feedback"]["timestamp"])
            self.assertEqual(imported.messages(imported_id)[1]["failure_category"], "Requirement missed")
            with self.assertRaisesRegex(ValueError, "already exists"):
                imported.import_json(json.dumps(payload))
            default_export = original.export_json(session)
            self.assertNotIn("abcdefghijklmnop1234", default_export)
            self.assertNotIn("alice", default_export)
            self.assertIn("[REDACTED PATH]", default_export)
            markdown = original.export_markdown(session, redact=False)
            self.assertIn(content, markdown)
            self.assertIn("No GUI preview", markdown)

    def test_empty_session_and_details_toggle(self):
        with tempfile.TemporaryDirectory() as temp:
            store = ChatStore(Path(temp) / "chat.sqlite3")
            session = store.create_session()
            self.assertEqual(json.loads(store.export_json(session))["messages"], [])
            message = store.add_message(session, "assistant", "Hello")
            store.save_feedback(message, 1, "Good")
            payload = json.loads(store.export_json(session, include_details=False))
            self.assertNotIn("feedback", payload["messages"][0])
            self.assertNotIn("metadata", payload["messages"][0])

    def test_evaluation_queue_snapshots_exact_response_without_execution(self):
        prompt, code = report_case("002")
        with tempfile.TemporaryDirectory() as temp:
            store = ChatStore(Path(temp) / "chat.sqlite3")
            session = store.create_session()
            store.add_message(session, "user", prompt)
            response_id = store.add_message(session, "assistant", code)
            case_id = store.queue_evaluation_case(response_id)
            self.assertEqual(store.queue_evaluation_case(response_id), case_id)
            case = store.evaluation_cases()[0]
            self.assertEqual(case["prompt"], prompt)
            self.assertEqual(case["response"], code)
            self.assertEqual(case["status"], "static_reviewed")
            self.assertEqual(case["review"]["syntax"], "static_evidence")
            self.assertEqual(len(store.evaluation_cases()), 1)

    def test_problem_report_is_linked_editable_and_exported(self):
        with tempfile.TemporaryDirectory() as temp:
            store = ChatStore(Path(temp) / "chat.sqlite3")
            session = store.create_session()
            user_id = store.add_message(session, "user", "Build a Tkinter app")
            assistant_id = store.add_message(session, "assistant", "Original code")
            with self.assertRaises(ValueError):
                store.save_problem_report(user_id, actual="Wrong")
            with self.assertRaises(ValueError):
                store.save_problem_report(assistant_id)
            store.save_problem_report(assistant_id, "GUI preview", "Console output", "NameError: missing")
            created_at = store.messages(session)[1]["problem_created_at"]
            store.save_problem_report(assistant_id, "GUI preview", "Still console output", "NameError: missing")
            self.assertEqual(store.messages(session)[1]["problem_created_at"], created_at)
            payload = json.loads(store.export_json(session, redact=False))
            problem = payload["messages"][1]["problem_report"]
            self.assertEqual(problem["message_id"], payload["messages"][1]["id"])
            self.assertEqual(problem["actual"], "Still console output")
            imported = ChatStore(Path(temp) / "import.sqlite3")
            imported_session = imported.import_json(json.dumps(payload))
            self.assertEqual(imported.messages(imported_session)[1]["problem_traceback"], "NameError: missing")
            self.assertEqual(imported.messages(imported_session)[1]["content"], "Original code")

    def test_queue_keeps_correction_context(self):
        with tempfile.TemporaryDirectory() as temp:
            store = ChatStore(Path(temp) / "chat.sqlite3")
            session = store.create_session()
            original = "Create a task manager showing CPU GPU RAM live usage, using Tkinter or PyQt"
            store.add_message(session, "user", original)
            store.add_message(session, "assistant", "First draft")
            store.add_message(session, "user", "Do not use PyQt, just use Tkinter and live graphs")
            response = store.add_message(session, "assistant", "from PyQt5.QtWidgets import QWidget")
            store.queue_evaluation_case(response)
            case = store.evaluation_cases()[0]
            self.assertEqual(case["context"], [original])
            self.assertEqual(case["review"]["requirements"][0]["status"], "failed")

    def test_legacy_database_migration_preserves_feedback(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "legacy.sqlite3"
            db = sqlite3.connect(path)
            db.executescript("""
                CREATE TABLE sessions(id INTEGER PRIMARY KEY,title TEXT NOT NULL,created_at TEXT NOT NULL,updated_at TEXT NOT NULL);
                CREATE TABLE messages(id INTEGER PRIMARY KEY,session_id INTEGER NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
                    role TEXT NOT NULL,content TEXT NOT NULL,model TEXT,profile TEXT,metrics_json TEXT,created_at TEXT NOT NULL);
                CREATE TABLE feedback(message_id INTEGER PRIMARY KEY REFERENCES messages(id) ON DELETE CASCADE,
                    rating INTEGER NOT NULL,comment TEXT NOT NULL,candidate INTEGER NOT NULL,updated_at TEXT NOT NULL);
                INSERT INTO sessions VALUES(1,'Old','2026-01-01T00:00:00+00:00','2026-01-01T00:00:00+00:00');
                INSERT INTO messages VALUES(7,1,'assistant','Old answer','unknown',NULL,NULL,'2026-01-01T00:00:00+00:00');
                INSERT INTO feedback VALUES(7,-1,'Old note',0,'2026-01-01T00:00:00+00:00');
                PRAGMA user_version=1;
            """)
            db.close()
            store = ChatStore(path)
            row = store.messages(1)[0]
            self.assertEqual(row["content"], "Old answer")
            self.assertEqual(row["comment"], "Old note")
            UUID(row["public_id"])
            self.assertEqual(ChatStore(path).messages(1)[0]["public_id"], row["public_id"])

    def test_reported_responses_are_static_evidence_only(self):
        sort_prompt, sort_code = report_case("001")
        sort_result = review_requirements(sort_prompt, sort_code)
        sort_status = {item["id"]: item["status"] for item in sort_result["requirements"]}
        self.assertEqual(sort_status["no_builtin_sort"], "static_evidence")
        self.assertEqual(sort_status["sort_list"], "unknown")
        gui_prompt, gui_code = report_case("002")
        gui_result = review_requirements(gui_prompt, gui_code)
        gui_status = {item["id"]: item["status"] for item in gui_result["requirements"]}
        self.assertEqual(gui_status["folder_select"], "static_evidence")
        for key in ("gui_file_preview", "gui_name_edit", "preview_before_apply", "confirmation"):
            self.assertEqual(gui_status[key], "failed")
        self.assertEqual(gui_status["collision_guard"], "unknown")

    def test_unrelated_console_debug_is_not_misclassified_as_gui_interaction(self):
        prompt = "Make a tkinter app to rename files with a preview"
        code = """import tkinter as tk
def debug():
    print("development only")
    input("development only")
def choose():
    pass
root = tk.Tk()
tk.Button(root, command=choose)
"""
        statuses = {item["id"]: item["status"] for item in review_requirements(prompt, code)["requirements"]}
        self.assertEqual(statuses["gui_file_preview"], "unknown")
        self.assertEqual(statuses["gui_name_edit"], "unknown")

    def test_import_rejects_detached_feedback(self):
        with tempfile.TemporaryDirectory() as temp:
            store = ChatStore(Path(temp) / "chat.sqlite3")
            session = store.create_session()
            mid = store.add_message(session, "assistant", "Answer")
            store.save_feedback(mid, 1)
            payload = json.loads(store.export_json(session))
            payload["messages"][0]["feedback"]["message_id"] = payload["session"]["id"]
            with self.assertRaisesRegex(ValueError, "mismatch"):
                parse_export(json.dumps(payload))
            payload["messages"][0]["feedback"] = "up"
            with self.assertRaisesRegex(ValueError, "invalid feedback"):
                parse_export(json.dumps(payload))

    def test_redaction_covers_quoted_credentials_bearer_and_spaced_paths(self):
        with tempfile.TemporaryDirectory() as temp:
            store = ChatStore(Path(temp) / "chat.sqlite3")
            session = store.create_session()
            store.add_message(session, "user",
                              'api_key = "private123"\n{"password": "hidden456"}\n'
                              'Bearer abc.def.ghi\n"C:\\Users\\Alice Smith\\file.py"')
            exported = store.export_json(session)
            for secret in ("private123", "hidden456", "abc.def.ghi", "Alice Smith"):
                self.assertNotIn(secret, exported)
            self.assertEqual(exported.count("[REDACTED SECRET]"), 3)
            self.assertIn("[REDACTED PATH]", exported)


if __name__ == "__main__":
    unittest.main()
