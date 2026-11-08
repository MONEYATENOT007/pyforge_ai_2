import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from pyforge.chat.store import ChatStore
from pyforge import __version__
from pyforge.models.client import ModelChunk

try:
    from streamlit.testing.v1 import AppTest
except ImportError:
    AppTest = None


APP = Path(__file__).resolve().parent.parent / "pyforge/ui/app.py"


@unittest.skipUnless(AppTest is not None, "Streamlit UI extra is not installed")
class UiTests(unittest.TestCase):
    def test_chat_playground_renders_with_local_model_list(self):
        with tempfile.TemporaryDirectory() as temp, patch.dict(os.environ, {"PYFORGE_DATA_ROOT": temp}), patch("pyforge.models.ollama_client.OllamaClient.list_models", return_value=["fake-local"]):
            app = AppTest.from_file(str(APP)).run(timeout=20)
            self.assertEqual(len(app.exception), 0, [item.message for item in app.exception])
            self.assertIn("PyForge AI", [item.value for item in app.title])
            self.assertIn(f"PyForge AI · v{__version__}", [item.value for item in app.title])
            self.assertTrue(any(item.label == "Installed model" for item in app.selectbox))
            self.assertTrue(any(item.label == "Redact potential secrets" and item.value for item in app.checkbox))

    def test_user_can_send_streamed_message_and_reopen_history(self):
        def fake_stream(_client, messages, *, context):
            self.assertEqual(messages[-1]["content"], "Explain a list")
            yield ModelChunk(text="A list stores values.")
            yield ModelChunk(done=True, prompt_tokens=8, output_tokens=5, total_seconds=0.2, generation_seconds=0.1)

        with tempfile.TemporaryDirectory() as temp, patch.dict(os.environ, {"PYFORGE_DATA_ROOT": temp}), patch("pyforge.models.ollama_client.OllamaClient.list_models", return_value=["fake-local"]), patch("pyforge.models.ollama_client.OllamaClient.chat_stream", fake_stream):
            app = AppTest.from_file(str(APP)).run(timeout=20)
            app.text_area[0].set_value("Explain a list")
            app.button(key="FormSubmitter:compose-Send").click()
            app.run(timeout=20)
            self.assertEqual(len(app.exception), 0, [item.message for item in app.exception])
            store = ChatStore(Path(temp) / "chat.sqlite3")
            session = store.list_sessions()[0]["id"]
            messages = store.messages(session)
            self.assertEqual([item["role"] for item in messages], ["user", "assistant"], [(item.value if hasattr(item, "value") else "") for item in app.warning])
            self.assertEqual(messages[1]["content"], "A list stores values.")
            self.assertEqual(messages[1]["metrics"]["status"], "complete")
            assistant_id = messages[1]["id"]
            app.button(key=f"queue_{assistant_id}").click()
            app.run(timeout=20)
            self.assertEqual(store.evaluation_cases()[0]["message_id"], assistant_id)
            self.assertEqual(store.evaluation_cases()[0]["status"], "static_reviewed")
            next(item for item in app.selectbox if item.label == "Rating").set_value("👎")
            next(item for item in app.text_area if item.label == "Correction or comment").set_value("Needs an example")
            next(item for item in app.checkbox if item.label.startswith("Save as future training candidate")).set_value(True)
            app.button(key=f"feedback_{assistant_id}").click()
            app.run(timeout=20)
            self.assertEqual(len(app.exception), 0, [item.message for item in app.exception])
            saved = store.messages(session)[1]
            self.assertEqual((saved["rating"], saved["comment"], saved["candidate"]), (-1, "Needs an example", 1))
            app = AppTest.from_file(str(APP)).run(timeout=20)
            self.assertTrue(any("A list stores values." in item.value for item in app.markdown))
