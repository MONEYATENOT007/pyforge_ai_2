from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from pyforge.chat.service import stream_exchange
from pyforge.chat.store import ChatStore
from pyforge.models.client import ModelChunk
from pyforge.models.ollama_client import OllamaClient


class StreamClient:
    model = "fake-local"

    def __init__(self, fail: bool = False):
        self.fail = fail
        self.seen = None

    def chat_stream(self, messages, *, context):
        self.seen = (messages, context)
        yield ModelChunk(text="partial")
        if self.fail:
            raise RuntimeError("connection lost")
        yield ModelChunk(text=" answer")
        yield ModelChunk(done=True, prompt_tokens=12, output_tokens=2, total_seconds=1.0, generation_seconds=0.5)


class ChatServiceTests(unittest.TestCase):
    def test_completed_stream_persists_roles_and_metrics(self):
        with tempfile.TemporaryDirectory() as temp:
            store = ChatStore(Path(temp) / "chat.sqlite3")
            session = store.create_session()
            client = StreamClient()
            chunks = list(stream_exchange(store, client, session, "Question", "Core", 2048))
            messages = store.messages(session)
            self.assertEqual("".join(chunk.text for chunk in chunks), "partial answer")
            self.assertEqual([row["role"] for row in messages], ["user", "assistant"])
            self.assertEqual(messages[1]["content"], "partial answer")
            self.assertEqual(messages[1]["metrics"]["status"], "complete")
            self.assertEqual(messages[1]["metrics"]["output_tokens"], 2)
            self.assertEqual(messages[1]["metrics"]["context"], 2048)
            self.assertIsNotNone(messages[1]["metrics"]["time_to_first_token_seconds"])
            self.assertEqual(client.seen[1], 2048)
            self.assertEqual(client.seen[0][-1]["content"], "Question")

    def test_interrupted_stream_is_saved_as_incomplete(self):
        with tempfile.TemporaryDirectory() as temp:
            store = ChatStore(Path(temp) / "chat.sqlite3")
            session = store.create_session()
            with self.assertRaisesRegex(RuntimeError, "connection lost"):
                list(stream_exchange(store, StreamClient(fail=True), session, "Question", "General"))
            messages = store.messages(session)
            self.assertEqual(messages[1]["content"], "partial")
            self.assertEqual(messages[1]["metrics"]["status"], "interrupted")

    def test_ollama_turn_records_provenance_and_requirement_checklist(self):
        with tempfile.TemporaryDirectory() as temp:
            store = ChatStore(Path(temp) / "chat.sqlite3")
            session = store.create_session()
            client = OllamaClient("local:model")
            metadata = {"model_digest": "digest123", "quantization": "Q4_K_M",
                        "runtime_version": "0.40.14"}
            with patch.object(client, "model_metadata", return_value=metadata), patch.object(
                client, "chat_stream", return_value=iter([ModelChunk(text="code"),
                                                           ModelChunk(done=True, output_tokens=1)])
            ) as stream:
                list(stream_exchange(store, client, session,
                                     "make me an app using tkinter only which renames files in a folder with preview",
                                     "General", 4096))
            sent = stream.call_args.args[0]
            self.assertIn("Populate an in-GUI file preview", sent[0]["content"])
            saved = store.messages(session)[1]
            self.assertEqual(saved["run"]["model_digest"], "digest123")
            self.assertEqual(saved["run"]["quantization"], "Q4_K_M")
            self.assertEqual(saved["run"]["runtime_version"], "0.40.14")
            self.assertEqual(saved["run"]["system_prompt"], sent[0]["content"])
            self.assertTrue(saved["run"]["requirements_checklist"])

    def test_output_limit_is_recorded_as_incomplete(self):
        with tempfile.TemporaryDirectory() as temp:
            store = ChatStore(Path(temp) / "chat.sqlite3")
            session = store.create_session()
            client = OllamaClient("local:model", max_output_tokens=768)
            with patch.object(client, "model_metadata", return_value={}), patch.object(
                client, "chat_stream", return_value=iter([ModelChunk(text="partial code"),
                                                           ModelChunk(done=True, output_tokens=768, done_reason="length")])
            ):
                list(stream_exchange(store, client, session, "Make a GUI", "General"))
            saved = store.messages(session)[1]
            self.assertEqual(saved["metrics"]["status"], "output_limited")
            self.assertEqual(saved["metrics"]["done_reason"], "length")
            self.assertEqual(saved["run"]["max_output_tokens"], 768)
