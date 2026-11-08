from pathlib import Path
import tempfile
import unittest

from pyforge.chat.service import stream_exchange
from pyforge.chat.store import ChatStore
from pyforge.models.client import ModelChunk


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
