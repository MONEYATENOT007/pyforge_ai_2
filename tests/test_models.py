from contextlib import contextmanager
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import threading
import unittest
from unittest.mock import patch
from urllib.error import HTTPError, URLError

from pyforge.models.fake_client import FakeClient
from pyforge.models.ollama_client import ModelUnavailable, OllamaClient


@contextmanager
def local_ollama_response(status=200, body=b'{}'):
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            self.server.last_path = self.path
            self.send_response(self.server.reply_status)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(self.server.reply_body)

        def do_POST(self):
            self.server.last_path = self.path
            self.server.last_body = self.rfile.read(int(self.headers["Content-Length"]))
            self.send_response(self.server.reply_status)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(self.server.reply_body)

        def log_message(self, format, *args):
            pass

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    server.reply_status = status
    server.reply_body = body
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield server
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)


class ModelTests(unittest.TestCase):
    def test_fake_reply_is_deterministic(self):
        client = FakeClient("ready")
        self.assertEqual(client.generate("hello").text, client.generate("hello").text)

    def test_non_loopback_urls_are_rejected(self):
        for url in ("https://127.0.0.1:11434", "http://example.com:11434", "http://localhost.evil:11434", "http://0.0.0.0:11434", "http://127.0.0.1:11434/evil", "http://user@localhost:11434"):
            with self.subTest(url=url), self.assertRaises(ValueError):
                OllamaClient("test", url)

    def test_cloud_model_tag_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "Cloud model"):
            OllamaClient("remote:cloud")

    def test_missing_model_is_friendly(self):
        client = OllamaClient("absent")
        error = HTTPError(client.url, 404, "missing", {}, None)
        with patch.object(client._opener, "open", side_effect=error):
            with self.assertRaisesRegex(ModelUnavailable, "absent"):
                client.generate("hello")

    def test_local_server_unavailable_is_friendly(self):
        client = OllamaClient("test")
        with patch.object(client._opener, "open", side_effect=URLError("offline")):
            with self.assertRaisesRegex(ModelUnavailable, "Local Ollama"):
                client.generate("hello")

    def test_real_loopback_http_exchange_uses_expected_request_and_metadata(self):
        body = json.dumps({"response": "ready", "prompt_eval_count": 7, "eval_count": 2}).encode()
        with local_ollama_response(body=body) as server:
            client = OllamaClient("test-model", f"http://127.0.0.1:{server.server_port}", context=1024)
            reply = client.generate("say ready")
            sent = json.loads(server.last_body)
            self.assertEqual(server.last_path, "/api/generate")
            self.assertEqual(sent["model"], "test-model")
            self.assertEqual(sent["options"], {"num_ctx": 1024, "temperature": 0})
            self.assertFalse(sent["stream"])
            self.assertEqual((reply.text, reply.prompt_tokens, reply.output_tokens), ("ready", 7, 2))
            self.assertGreaterEqual(reply.latency_seconds, 0)

    def test_real_loopback_http_errors_are_handled(self):
        with local_ollama_response(status=404, body=b'{"error":"not found"}') as server:
            client = OllamaClient("missing", f"http://127.0.0.1:{server.server_port}")
            with self.assertRaisesRegex(ModelUnavailable, "missing"):
                client.generate("hello")
        with local_ollama_response(body=b'not json') as server:
            client = OllamaClient("test", f"http://127.0.0.1:{server.server_port}")
            with self.assertRaisesRegex(ModelUnavailable, "invalid JSON"):
                client.generate("hello")

    def test_model_list_and_streaming_chat_over_loopback(self):
        with local_ollama_response(body=b'{"models":[{"name":"z:1b"},{"name":"a:1b"},{"name":"remote:cloud"}]}') as server:
            client = OllamaClient("a:1b", f"http://127.0.0.1:{server.server_port}")
            self.assertEqual(client.list_models(), ["a:1b", "z:1b"])
            self.assertEqual(server.last_path, "/api/tags")
        events = b'{"message":{"content":"hello"},"done":false}\n{"message":{"content":" world"},"done":false}\n{"message":{"content":""},"done":true,"prompt_eval_count":5,"eval_count":2,"total_duration":1000000000,"eval_duration":500000000}\n'
        with local_ollama_response(body=events) as server:
            client = OllamaClient("a:1b", f"http://127.0.0.1:{server.server_port}")
            chunks = list(client.chat_stream([{"role": "user", "content": "greet"}]))
            self.assertEqual("".join(chunk.text for chunk in chunks), "hello world")
            self.assertTrue(chunks[-1].done)
            self.assertEqual((chunks[-1].prompt_tokens, chunks[-1].output_tokens), (5, 2))
            self.assertEqual(json.loads(server.last_body)["messages"][0]["content"], "greet")

    def test_interrupted_stream_is_not_reported_as_complete(self):
        with local_ollama_response(body=b'{"message":{"content":"partial"},"done":false}\n') as server:
            client = OllamaClient("a:1b", f"http://127.0.0.1:{server.server_port}")
            with self.assertRaisesRegex(ModelUnavailable, "before completion"):
                list(client.chat_stream([{"role": "user", "content": "greet"}]))
