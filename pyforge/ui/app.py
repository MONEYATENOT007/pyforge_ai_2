"""Chat playground. Start with `python -m streamlit run pyforge/ui/app.py`."""

import os
from pathlib import Path

from pyforge import __version__
from pyforge.chat.profiles import PROFILES
from pyforge.chat.service import stream_exchange
from pyforge.chat.store import ChatStore
from pyforge.doctor import _gpu, _loaded_models
from pyforge.evaluation.requirements import review_requirements
from pyforge.models.ollama_client import ModelUnavailable, OllamaClient


def _data_root() -> Path:
    configured = os.environ.get("PYFORGE_DATA_ROOT")
    return Path(configured).expanduser().absolute() if configured else Path(__file__).resolve().parents[2] / "local_runtime" / "data"


def _metric_text(message: dict) -> str:
    metrics = message.get("metrics") or {}
    if metrics.get("status") == "interrupted":
        return "Interrupted response; content may be incomplete"
    if metrics.get("status") != "complete":
        return "Not automatically tested"
    tokens = metrics.get("output_tokens")
    seconds = metrics.get("generation_seconds")
    speed = f" · {tokens / seconds:.1f} tokens/s" if isinstance(tokens, int) and isinstance(seconds, (int, float)) and seconds > 0 else ""
    first = metrics.get("time_to_first_token_seconds")
    first_text = f" · first token {first:.2f}s" if isinstance(first, (int, float)) else ""
    return f"{message.get('model') or 'local model'} · context {metrics.get('context', '?')} · {tokens if tokens is not None else '?'} output tokens{speed}{first_text} · Not automatically tested"


def main() -> None:
    import streamlit as st

    st.set_page_config(page_title=f"PyForge AI v{__version__}", page_icon="🐍", layout="wide")
    store = ChatStore(_data_root() / "chat.sqlite3")
    sessions = store.list_sessions()
    if not sessions:
        store.create_session()
        sessions = store.list_sessions()
    ids = {row["id"] for row in sessions}
    if st.session_state.get("active_session") not in ids:
        st.session_state.active_session = sessions[0]["id"]

    with st.sidebar:
        st.title("PyForge AI")
        st.caption(f"Version {__version__}")
        st.caption("Local chat playground · generated code is not executed")
        if st.button("＋ New chat", use_container_width=True):
            st.session_state.active_session = store.create_session()
            st.rerun()
        for row in sessions:
            if st.button(row["title"], key=f"open_{row['id']}", use_container_width=True):
                st.session_state.active_session = row["id"]
                st.rerun()
        session_id = st.session_state.active_session
        selected_session = next(row for row in sessions if row["id"] == session_id)
        with st.expander("Manage this chat"):
            title = st.text_input("Title", value=selected_session["title"], key=f"title_{session_id}")
            if st.button("Rename", key=f"rename_{session_id}"):
                try:
                    store.rename_session(session_id, title)
                    st.rerun()
                except ValueError as exc:
                    st.error(str(exc))
            confirm_delete = st.checkbox("Confirm deletion", key=f"confirm_delete_{session_id}")
            if st.button("Delete chat", disabled=not confirm_delete, key=f"delete_{session_id}"):
                store.delete_session(session_id)
                remaining = store.list_sessions()
                st.session_state.active_session = remaining[0]["id"] if remaining else store.create_session()
                st.rerun()
        st.divider()
        endpoint = os.environ.get("PYFORGE_OLLAMA_URL", "http://127.0.0.1:11434")
        try:
            probe = OllamaClient("probe", endpoint, timeout=10)
            models = probe.list_models()
            st.success("Ollama connected on loopback")
        except (ModelUnavailable, ValueError) as exc:
            models = []
            st.warning(f"Ollama unavailable: {exc}")
        model = st.selectbox("Installed model", models, disabled=not models)
        profile = st.selectbox("Role profile", list(PROFILES))
        context = st.select_slider("Context limit", options=[1024, 2048, 4096], value=4096)
        st.caption("Roles change instructions, not model weights. One local model is active at a time.")
        loaded = _loaded_models()
        if loaded:
            for item in loaded:
                vram = item.get("size_vram_bytes")
                vram_text = f"{vram / (1024 ** 3):.2f} GiB VRAM" if isinstance(vram, int) else "VRAM unknown"
                st.caption(f"Loaded: {item.get('name')} · Ollama reports {vram_text}")
        else:
            st.caption("No loaded model reported; a cold request may take longer")
        gpu = _gpu()
        if gpu.get("status") == "ok":
            st.caption(f"GPU snapshot: {', '.join(gpu['gpus'])} (MiB total/free, then driver version)")
        st.caption("VRAM snapshots do not prove that every layer runs on GPU; inspect Ollama residency when measuring offload.")
        st.divider()
        with st.expander("Export session"):
            redact = st.checkbox("Redact potential secrets", value=True, key=f"redact_{session_id}")
            details = st.checkbox("Include feedback/metadata", value=True, key=f"details_{session_id}")
            stamp = selected_session["updated_at"][:10].replace("-", "")
            short_id = selected_session["public_id"][:8]
            name = f"pyforge-chat-{stamp}-{short_id}"
            markdown = store.export_markdown(session_id, redact=redact, include_details=details)
            st.download_button("Download Markdown", markdown, file_name=name + ".md", mime="text/markdown", use_container_width=True)
            st.download_button("Download JSON", store.export_json(session_id, redact=redact, include_details=details), file_name=name + ".json", mime="application/json", use_container_width=True)
            st.caption("Preview and copy Markdown below. Redaction is pattern-based; review private content before sharing.")
            st.code(markdown, language="markdown")

    st.title(f"PyForge AI · v{__version__}")
    st.subheader(selected_session["title"])
    st.caption("Local Ollama endpoint · our portable launcher disables cloud features · no automatic code execution or test claims")
    history = store.messages(session_id)
    user_prompts: list[str] = []
    for message in history:
        if message["role"] == "user":
            user_prompts.append(message["content"])
        with st.chat_message(message["role"]):
            st.markdown(message["content"])
            if message["role"] == "assistant":
                st.caption(_metric_text(message))
                prompt_text = user_prompts[-1] if user_prompts else ""
                static_review = review_requirements(prompt_text, message["content"], context=user_prompts[:-1])
                failed_checks = [item["id"] for item in static_review["requirements"] if item["status"] == "failed"]
                if failed_checks:
                    st.warning(f"Static review flagged: {', '.join(failed_checks)}. Generated code was not run.")
                with st.expander("Requirement review", expanded=False):
                    st.caption("Static inspection only. No generated code is run.")
                    if st.button("Review requirements", key=f"review_{message['id']}"):
                        st.session_state[f"review_result_{message['id']}"] = static_review
                    review = st.session_state.get(f"review_result_{message['id']}")
                    if review:
                        st.write(review)
                    if st.button("Add to evaluation queue", key=f"queue_{message['id']}"):
                        try:
                            case_id = store.queue_evaluation_case(message["id"])
                            st.success(f"Saved analysis-only case {case_id[:8]}")
                        except ValueError as exc:
                            st.error(str(exc))
                    st.button("Run Tests", disabled=True, key=f"run_tests_{message['id']}")
                    st.caption("Isolated execution backend is not configured.")
                with st.expander("Feedback", expanded=False):
                    rating_options = ["Unrated", "👍", "👎"]
                    current = 1 if message["rating"] == 1 else 2 if message["rating"] == -1 else 0
                    rating = st.selectbox("Rating", rating_options, index=current, key=f"rating_{message['id']}")
                    comment = st.text_area("Correction or comment", value=message["comment"] or "", key=f"comment_{message['id']}")
                    categories = ["", "Requirement missed", "Incorrect code", "Unsafe file operation", "Other"]
                    selected_category = message.get("failure_category") or ""
                    category = st.selectbox("Failure category (optional)", categories,
                                            index=categories.index(selected_category) if selected_category in categories else 0,
                                            key=f"category_{message['id']}")
                    candidate = st.checkbox("Save as future training candidate (requires later review)", value=bool(message["candidate"]), key=f"candidate_{message['id']}")
                    if st.button("Save feedback", key=f"feedback_{message['id']}"):
                        if rating == "Unrated":
                            st.error("Choose thumbs up or down before saving")
                        else:
                            store.save_feedback(message["id"], 1 if rating == "👍" else -1, comment, candidate, category)
                            st.success("Saved locally")
                with st.expander("Report a problem", expanded=False):
                    st.caption("Linked to this exact response. Original code remains in the chat.")
                    expected = st.text_area("Expected behavior", value=message.get("problem_expected") or "",
                                            key=f"expected_{message['id']}")
                    actual = st.text_area("Actual behavior", value=message.get("problem_actual") or "",
                                          key=f"actual_{message['id']}")
                    traceback = st.text_area("Traceback or error", value=message.get("problem_traceback") or "",
                                             key=f"traceback_{message['id']}")
                    if st.button("Save problem report", key=f"problem_{message['id']}"):
                        try:
                            store.save_problem_report(message["id"], expected, actual, traceback)
                            st.success("Problem report saved locally")
                        except ValueError as exc:
                            st.error(str(exc))

    with st.form("compose", clear_on_submit=True):
        prompt = st.text_area("Message", placeholder="Ask about Python, paste code, or describe a traceback…", height=120)
        submitted = st.form_submit_button("Send", disabled=not models)
    if submitted and prompt.strip() and model:
        with st.chat_message("user"):
            st.markdown(prompt)
        with st.chat_message("assistant"):
            client = OllamaClient(model, endpoint, timeout=180, context=context)
            try:
                def text_stream():
                    for chunk in stream_exchange(store, client, session_id, prompt, profile, context):
                        if chunk.text:
                            yield chunk.text
                with st.spinner("Generating locally…"):
                    st.write_stream(text_stream())
                st.rerun()
            except (ModelUnavailable, RuntimeError, OSError, ValueError) as exc:
                st.error(f"Local response interrupted: {exc}. Any partial text is marked incomplete in chat history.")
    elif submitted:
        st.warning("Enter a message before sending")


if __name__ == "__main__":
    main()
