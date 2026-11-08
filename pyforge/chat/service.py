"""Persist a streamed exchange, including honest interrupted status."""

import time

from .profiles import build_chat_messages
from .store import ChatStore
from pyforge.models.client import ModelChunk
from pyforge.models.ollama_client import OllamaClient
from pyforge.evaluation.requirements import CHECKER_VERSION, extract_requirements


def stream_exchange(store: ChatStore, client, session_id: int, prompt: str, profile: str, context: int = 4096):
    history = store.messages(session_id)
    messages = build_chat_messages(history, prompt, profile, max_chars=min(12000, context * 2))
    criteria = extract_requirements(prompt, [row["content"] for row in history if row["role"] == "user"])
    if criteria:
        checklist = "\n".join(f"- [{item['origin']}] {item['criterion']}" for item in criteria)
        messages[0]["content"] += (
            "\n\nCheck this request against these requirements before answering. "
            "Use GUI widgets for GUI interactions, identify unsupported requirements, "
            "and never claim execution or tests you did not run:\n" + checklist
        )
    store.add_message(session_id, "user", prompt)
    is_ollama = isinstance(client, OllamaClient)
    provenance = client.model_metadata() if is_ollama else {}
    run = {
        "backend": "ollama" if is_ollama else "unknown",
        "model_digest": "unknown",
        "quantization": "unknown",
        "runtime_version": "unknown",
        "context_tokens": context,
        "temperature": 0 if is_ollama else "unknown",
        "max_output_tokens": client.max_output_tokens if is_ollama and client.max_output_tokens is not None else "unknown",
        "top_p": "unknown",
        "seed": "unknown",
        "system_prompt": messages[0]["content"],
        "profile": profile,
        "test_suite_version": "unknown",
        "requirements_checker_version": CHECKER_VERSION,
        "requirements_checklist": criteria,
    }
    run.update(provenance)
    pieces: list[str] = []
    final: ModelChunk | None = None
    started = time.perf_counter()
    first_token_seconds: float | None = None
    try:
        for chunk in client.chat_stream(messages, context=context):
            if chunk.text:
                if first_token_seconds is None:
                    first_token_seconds = time.perf_counter() - started
                pieces.append(chunk.text)
            if chunk.done:
                final = chunk
            yield chunk
        if final is None:
            raise RuntimeError("Model stream ended without completion")
    except Exception:
        if pieces:
            store.add_message(session_id, "assistant", "".join(pieces), model=client.model, profile=profile, run=run, metrics={"status": "interrupted", "context": context, "time_to_first_token_seconds": first_token_seconds})
        raise
    store.add_message(session_id, "assistant", "".join(pieces) or "(empty response)", model=client.model, profile=profile, run=run, metrics={"status": "output_limited" if final.done_reason == "length" else "complete", "done_reason": final.done_reason or "unknown", "context": context, "time_to_first_token_seconds": first_token_seconds, "prompt_tokens": final.prompt_tokens, "output_tokens": final.output_tokens, "total_seconds": final.total_seconds, "load_seconds": final.load_seconds, "generation_seconds": final.generation_seconds})
