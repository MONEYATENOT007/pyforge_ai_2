import json
from pathlib import Path
import sqlite3
import tempfile
import unittest

from pyforge.chat.profiles import build_chat_messages
from pyforge.chat.store import ChatStore


class ChatStoreTests(unittest.TestCase):
    def test_session_messages_feedback_export_and_delete(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "chat.sqlite3"
            store = ChatStore(path)
            session = store.create_session("  Example  ")
            user_id = store.add_message(session, "user", "Sort a list")
            assistant_id = store.add_message(session, "assistant", "Use sorted(values)", model="local", profile="Core", metrics={"tokens": 4})
            store.save_feedback(assistant_id, -1, "Missed constraint", candidate=False)
            self.assertEqual(store.list_sessions()[0]["title"], "Example")
            self.assertEqual(store.messages(session)[1]["rating"], -1)
            self.assertEqual(store.messages(session)[1]["candidate"], 0)
            self.assertEqual(store.messages(session)[1]["metrics"], {"tokens": 4})
            self.assertEqual(store.messages(session)[0]["id"], user_id)
            self.assertEqual(json.loads(store.export_json(session))["messages"][0]["id"], store.messages(session)[0]["public_id"])
            self.assertIn("Use sorted(values)", store.export_markdown(session))
            store.rename_session(session, "Renamed")
            self.assertEqual(store.list_sessions()[0]["title"], "Renamed")
            store.delete_session(session)
            db = sqlite3.connect(path)
            try:
                self.assertEqual(db.execute("SELECT count(*) FROM messages").fetchone()[0], 0)
                self.assertEqual(db.execute("SELECT count(*) FROM feedback").fetchone()[0], 0)
            finally:
                db.close()

    def test_feedback_requires_assistant_and_opt_in_is_explicit(self):
        with tempfile.TemporaryDirectory() as temp:
            store = ChatStore(Path(temp) / "chat.sqlite3")
            session = store.create_session()
            user_id = store.add_message(session, "user", "Hello")
            assistant_id = store.add_message(session, "assistant", "Hi")
            with self.assertRaises(ValueError):
                store.save_feedback(user_id, 1)
            with self.assertRaises(ValueError):
                store.save_feedback(assistant_id, 0)
            store.save_feedback(assistant_id, 1, "Good")
            self.assertEqual(store.messages(session)[1]["candidate"], 0)
            store.save_feedback(assistant_id, 1, "Good", candidate=True)
            self.assertEqual(store.messages(session)[1]["candidate"], 1)

    def test_newer_schema_is_refused(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "future.sqlite3"
            db = sqlite3.connect(path)
            try:
                db.execute("PRAGMA user_version = 99")
                db.commit()
            finally:
                db.close()
            with self.assertRaisesRegex(RuntimeError, "newer"):
                ChatStore(path)

    def test_history_budget_keeps_recent_messages_and_profile(self):
        history = [
            {"role": "user", "content": "old long message"},
            {"role": "assistant", "content": "recent"},
        ]
        messages = build_chat_messages(history, "current", "Core", max_chars=14)
        self.assertEqual([m["role"] for m in messages], ["system", "assistant", "user"])
        self.assertIn("Python core", messages[0]["content"])
        with self.assertRaises(ValueError):
            build_chat_messages([], "hello", "Missing")
        with self.assertRaisesRegex(ValueError, "too long"):
            build_chat_messages([], "a" * 15, "Core", max_chars=14)
