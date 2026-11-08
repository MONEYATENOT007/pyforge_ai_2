"""Deterministic model for tests and offline interface checks."""

from .client import ModelReply


class FakeClient:
    def __init__(self, response: str = "fake response") -> None:
        self.response = response

    def generate(self, prompt: str) -> ModelReply:
        return ModelReply(text=self.response, model="fake", prompt_tokens=len(prompt.split()), output_tokens=len(self.response.split()), latency_seconds=0.0)
