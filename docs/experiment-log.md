# Experiment log

Current first-user-test implementation progress is tracked in [experiment_log.md](experiment_log.md). This file retains the earlier Phase 0/1 observations.

## 2026-11-08 — preflight and baseline

- Windows 11, Python 3.14.10, 15.95 GiB RAM, RTX 2060 6 GiB observed; C: is an SSD per owner, F: approved for main project files, G: overflow. Details in `PHASE0_REPORT.md`.
- Portable Ollama 0.40.14 and Qwen2.5-Coder 1.5B Instruct Q4_K_M installed under `local_runtime/` on F:. Server logs confirmed `OLLAMA_MODELS` on F:, loopback bind and `OLLAMA_NO_CLOUD=1`.
- Initial cold request: 84.013 seconds. Warm 20-task runs: average request latencies 0.791, 0.877 and 0.800 seconds; zero generation failures. Two outputs changed in the third run despite temperature zero. Results and manual failure examples in `PHASE1_REPORT.md`. No generated code was executed.

## 2026-11-08 — revised Stage 1 slice

- Added SQLite sessions, messages and feedback, one shared model with role instructions, streaming Ollama chat and model listing, and a Streamlit chat page.
- Storage tests exposed unclosed SQLite connections on Windows; connection handling was corrected. The expanded suite passed 33 tests. Streamlit AppTest rendered the page and completed a mocked send, history reopen and feedback save. A real local stream returned `ready` and persisted a completed record with timing metadata.
- Streamlit 1.67.0 and its dependencies were installed into `.venv` on F:. The server was observed at `127.0.0.1:8501`, with HTTP 200 from its health and root endpoints. No browser-level visual walkthrough or internet-disconnected trial has been completed yet.
- The project environment occupied about 355.7 MiB at the last measurement. F: had about 213.38 GiB free and C: about 87.1 GiB free. The model/runtime archive remain on F:; G: was not used.
