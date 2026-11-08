"""Ollama adapter restricted to loopback HTTP."""

import json
import time
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import ProxyHandler, Request, build_opener

from .client import ModelChunk, ModelReply


class ModelUnavailable(RuntimeError):
    pass


def _cloud_tag(model: str) -> bool:
    return model.rsplit(":", 1)[-1].lower().endswith("cloud")


class OllamaClient:
    def __init__(self, model: str, url: str = "http://127.0.0.1:11434", timeout: float = 120, context: int = 4096) -> None:
        parsed = urlsplit(url)
        if parsed.scheme != "http" or parsed.hostname not in {"127.0.0.1", "localhost", "::1"} or parsed.username or parsed.password or parsed.path not in {"", "/"} or parsed.query or parsed.fragment:
            raise ValueError("Ollama URL must be a loopback HTTP origin")
        if not model or not model.strip():
            raise ValueError("model name is required")
        if _cloud_tag(model):
            raise ValueError("Cloud model tags are disabled in PyForge")
        if timeout <= 0 or context <= 0:
            raise ValueError("timeout and context must be positive")
        self.url = url.rstrip("/")
        self.model = model
        self.timeout = timeout
        self.context = context
        self._opener = build_opener(ProxyHandler({}))

    def list_models(self) -> list[str]:
        request = Request(self.url + "/api/tags", method="GET")
        try:
            with self._opener.open(request, timeout=min(self.timeout, 10)) as response:
                data = json.load(response)
        except (HTTPError, URLError, TimeoutError, OSError, ValueError) as exc:
            if isinstance(exc, HTTPError):
                exc.close()
            raise ModelUnavailable("Local Ollama model list is unavailable") from exc
        if not isinstance(data, dict) or not isinstance(data.get("models"), list):
            raise ModelUnavailable("Local Ollama returned an invalid model list")
        return sorted(item["name"] for item in data["models"] if isinstance(item, dict) and isinstance(item.get("name"), str) and not _cloud_tag(item["name"]))

    def chat_stream(self, messages: list[dict], *, context: int | None = None):
        if not messages or any(item.get("role") not in {"system", "user", "assistant"} or not isinstance(item.get("content"), str) for item in messages):
            raise ValueError("chat messages need valid roles and text content")
        size = self.context if context is None else context
        if size <= 0:
            raise ValueError("context must be positive")
        body = json.dumps({"model": self.model, "messages": messages, "stream": True, "options": {"num_ctx": size, "temperature": 0}}).encode("utf-8")
        request = Request(self.url + "/api/chat", data=body, headers={"Content-Type": "application/json"}, method="POST")
        try:
            with self._opener.open(request, timeout=self.timeout) as response:
                finished = False
                for line in response:
                    if not line.strip():
                        continue
                    item = json.loads(line)
                    if not isinstance(item, dict):
                        raise ModelUnavailable("Local Ollama returned an invalid stream event")
                    if item.get("error"):
                        raise ModelUnavailable(str(item["error"]))
                    message = item.get("message", {})
                    if not isinstance(message, dict) or not isinstance(message.get("content", ""), str):
                        raise ModelUnavailable("Local Ollama returned an invalid stream event")
                    done = bool(item.get("done"))
                    yield ModelChunk(
                        text=message.get("content", ""),
                        done=done,
                        prompt_tokens=item.get("prompt_eval_count") if done else None,
                        output_tokens=item.get("eval_count") if done else None,
                        total_seconds=item.get("total_duration", 0) / 1e9 if done else None,
                        load_seconds=item.get("load_duration", 0) / 1e9 if done else None,
                        generation_seconds=item.get("eval_duration", 0) / 1e9 if done else None,
                    )
                    if done:
                        finished = True
                        break
                if not finished:
                    raise ModelUnavailable("Local Ollama stream ended before completion")
        except HTTPError as exc:
            exc.close()
            if exc.code == 404:
                raise ModelUnavailable(f"Model '{self.model}' is absent in Ollama") from exc
            raise ModelUnavailable(f"Ollama returned HTTP {exc.code}") from exc
        except (URLError, TimeoutError, OSError) as exc:
            raise ModelUnavailable("Local Ollama stream was interrupted or unavailable") from exc
        except (ValueError, TypeError, KeyError) as exc:
            raise ModelUnavailable("Local Ollama returned invalid stream JSON") from exc

    def generate(self, prompt: str) -> ModelReply:
        body = json.dumps({"model": self.model, "prompt": prompt, "stream": False, "options": {"num_ctx": self.context, "temperature": 0}}).encode("utf-8")
        request = Request(self.url + "/api/generate", data=body, headers={"Content-Type": "application/json"}, method="POST")
        started = time.monotonic()
        try:
            with self._opener.open(request, timeout=self.timeout) as response:
                result = json.load(response)
        except HTTPError as exc:
            exc.close()
            if exc.code == 404:
                raise ModelUnavailable(f"Model '{self.model}' is absent in Ollama. Install it only after approving the model and storage location.") from exc
            raise ModelUnavailable(f"Ollama returned HTTP {exc.code}") from exc
        except (URLError, TimeoutError, OSError) as exc:
            raise ModelUnavailable("Local Ollama is unavailable. Start Ollama on loopback and check the configured URL.") from exc
        except (ValueError, TypeError) as exc:
            raise ModelUnavailable("Local Ollama returned invalid JSON") from exc
        if not isinstance(result, dict) or not isinstance(result.get("response"), str):
            raise ModelUnavailable("Local Ollama returned an unexpected response")
        return ModelReply(result["response"], self.model, result.get("prompt_eval_count"), result.get("eval_count"), time.monotonic() - started)
