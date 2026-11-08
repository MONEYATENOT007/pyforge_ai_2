"""Model client contract."""

from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class ModelReply:
    text: str
    model: str
    prompt_tokens: int | None = None
    output_tokens: int | None = None
    latency_seconds: float | None = None


@dataclass(frozen=True)
class ModelChunk:
    text: str = ""
    done: bool = False
    prompt_tokens: int | None = None
    output_tokens: int | None = None
    total_seconds: float | None = None
    load_seconds: float | None = None
    generation_seconds: float | None = None


class ModelClient(Protocol):
    def generate(self, prompt: str) -> ModelReply: ...
