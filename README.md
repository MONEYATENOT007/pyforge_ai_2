# PyForge AI

PyForge AI is an offline-first Python coding assistant under active development. The current working slice has a CLI, a local Ollama model, a Streamlit chat playground, SQLite chat history and feedback, and an early benchmark recorder. The [revised master plan](PYFORGE_AI_CODEX_REVISED_MASTER_PLAN.MD) defines the stage order. Generated code is **never executed** by the current app; automated editing and isolated testing are future work.

The local package version is kept in [pyforge/_version.py](pyforge/_version.py) and appears in the chat sidebar and `python -m pyforge --version`. The [progress ledger](progress.md) records completed work and open items against the project briefs; it is updated with each project change.

## Requirements and setup

- Python 3.11 or newer. On Windows, verify with `py -0p` or `python --version` before installation.
- The doctor and CLI use only Python's standard library. The UI uses Streamlit 1.67.0 and the pinned transitive versions in `requirements-ui.lock.txt`.
- The existing `.venv` on this PC is on F:. New installations should create the environment on an approved drive and check disk space first.

From the project root:

```powershell
python -m pyforge doctor
python -m pyforge doctor --json
python -m unittest discover -s tests -v
```

On the owner's current PC, `python` points to the Windows Store placeholder, while Python 3.14.10 is installed at `C:\Users\hrdkk\AppData\Local\Programs\Python\Python314\python.exe`. Use `& .\.venv\Scripts\python.exe -m pyforge doctor` from this project, or the full installed Python path. The revised UI requires Python 3.11+.

## Start the local chat playground

1. If Ollama is not already running, start the approved portable server: `powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\scripts\start_local_ollama.ps1`.
2. Start the UI: `powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\scripts\start_chat.ps1`.
3. Open `http://127.0.0.1:8501` in a browser. The UI stays on loopback. Press Ctrl+C in the UI terminal to stop its server.

Saved chat source changes rerun automatically through Streamlit's watcher. If port 8501 becomes unavailable or a change does not appear, use `powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\scripts\restart_chat.ps1`. This command checks that any process on port 8501 is this project's Streamlit server before replacing it, then waits for the health endpoint. The current PyForge version appears at the top of the page and in the browser tab title.

The UI shows installed local models, six instruction profiles, a 1024–4096 token context setting, streamed messages, local session history, editable response-linked feedback and selected-session JSON/Markdown exports. Exports default to pattern-based secret/path redaction and offer a Markdown preview; review private content before sharing. JSON exports use schema `1.0` and can be imported through `ChatStore.import_json`; an evaluation-lab import UI remains pending. Role profiles change instructions to the **same** model; they are not fine-tuned specialists. A response can be rated and optionally flagged as a *candidate* for later training review; feedback alone does not validate or train a model. Chat history lives in `local_runtime/data/chat.sqlite3` on F: by default. Set `PYFORGE_DATA_ROOT` for another approved local data directory. Deleting a session requires a visible confirmation checkbox.

Each assistant response has a static requirement review and an **Add to evaluation queue** action. The queue snapshots the preceding user prompt and exact response in SQLite without executing code. **Run Tests** is visible but disabled until an isolated runner is configured. The first user-observed examples are in [FIRST_TEST_RUN_BY_USER.md](FIRST_TEST_RUN_BY_USER.md); current implementation evidence is in [docs/experiment_log.md](docs/experiment_log.md).

For a fresh environment on an approved drive, create a virtual environment and install `.[ui]` using `requirements-ui.lock.txt` as constraints. On this PC, from the F: project root:

```powershell
& 'C:\Users\hrdkk\AppData\Local\Programs\Python\Python314\python.exe' -m venv .venv
& .\.venv\Scripts\python.exe -m pip install -e '.[ui]' -c requirements-ui.lock.txt
& .\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

Set `TEMP`, `TMP` and `PIP_CACHE_DIR` to approved F: directories before installing if C: space is tight. Normal use after installation and model download requires no internet. The launcher disables Streamlit usage statistics and the Ollama launcher disables Ollama cloud features. A different Ollama server on the same loopback port may have different cloud settings, so the UI identifies the local endpoint rather than claiming every server is offline.

### Learning notes

- The **model** is the downloaded set of weights that generates text. An **agent** adds software steps such as reading files, planning, testing and patching around a model. PyForge has chat and evaluation plumbing today; it does not yet have an autonomous repair agent.
- **4-bit quantization** stores most model weights compactly. Actual RAM/VRAM use is larger because the runtime also needs context cache and compute buffers. A 4096-token context does not mean a whole large repository can fit in one prompt.
- The six role choices are instructions to one shared model, not six trained specialists. A thumbs-up/down is local feedback and a training candidate is only a queue entry for future review.

## Storage approval workflow

1. Run `doctor` and inspect actual free space and available drives. It reports drive class (fixed/removable/network) but cannot reliably identify SSD versus HDD; verify physical media separately.
2. Choose approved fast, bulk, and workspace roots. Keep at least 50 GiB free on the fast OS drive and 40 GiB on secondary/bulk drives. The displayed budgets are soft planning limits, not reservations.
3. Copy `config/storage.example.json` to `config/storage.json` and set absolute roots, or set `PYFORGE_FAST_ROOT`, `PYFORGE_BULK_ROOT`, and `PYFORGE_WORKSPACE_ROOT` in your shell. No directories are created by `doctor`.
4. Rerun `doctor`; only then consider installation or model downloads. Store active models on the chosen fast root and archives on the approved bulk root. `OLLAMA_MODELS`, `HF_HOME`, and `HF_HUB_CACHE` can direct relevant caches; some runtime files may still use the OS drive.

The doctor tests whether a parent directory appears writable but performs no write probe. Network and optical drives are listed for visibility and are not proposed as allocation candidates. The current report does not reserve space or enforce budgets.

## Optional local model

The approved lightweight artifact is [`qwen2.5-coder:1.5b-instruct-q4_K_M`](https://ollama.com/library/qwen2.5-coder%3A1.5b-instruct): Ollama lists digest `d7372fd82851`, 986 MB model size, Q4_K_M quantization, and Apache 2.0 license. The [upstream Qwen 1.5B Instruct license](https://huggingface.co/Qwen/Qwen2.5-Coder-1.5B-Instruct/blob/cc932d8a05bf5a3dcd700f50584714d17fc4d03a/LICENSE) is also Apache 2.0. A 7B candidate should be benchmarked only after the lightweight baseline is practical.

On the current PC, Ollama 0.40.14 is extracted under `local_runtime/ollama` and the model is under `local_runtime/models`, both on F:. `local_runtime/` is ignored by Git. Start the portable server with:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\scripts\start_local_ollama.ps1
```

The launcher sets model and temporary directories under `local_runtime`, binds to `127.0.0.1`, and sets `OLLAMA_NO_CLOUD=1` for the server process. It does not set persistent Windows environment variables. It refuses to attach to a server already using the port because that server's model path may differ. Ollama also creates a small user key under the Windows profile. If a restricted shell blocks this, launch the script with the necessary local filesystem permission. The project does not currently install Ollama globally.

If PyForge is installed as a wheel outside this source folder, set `PYFORGE_OLLAMA_EXE` to the portable `ollama.exe` path when running `doctor`; the command reads that path but does not execute the binary.

```powershell
python -m pyforge chat "Write a Python function that adds two numbers"
```

`chat` uses only `http://127.0.0.1:11434` by default and rejects non-loopback URLs. Set `PYFORGE_OLLAMA_URL` or use `--url` for another local port. It uses 4096 context tokens by default. It does not execute model output. If Ollama or the model is missing, it exits with a clear error.

## Baseline benchmark

The package includes 20 fixed prompts in `pyforge/evaluation/tasks.json`. Run the deterministic smoke test without Ollama:

```powershell
python -m pyforge benchmark --fake --output results/fake-baseline.jsonl
```

For a real local model, omit `--fake` and use a new output filename for each run; the runner refuses to overwrite previous results. Each JSONL row stores the prompt, raw answer, available token counts and latency, and before/after RAM and VRAM samples. These samples are snapshots, not peak usage. Generated code is **not executed**; `test_result` is `not_run_no_isolated_executor`. The current fixture has manually written review criteria but no automated correctness grade. Model outputs require review until a secure isolated executor exists. The first real baseline is in `results/qwen-1.5b-baseline.jsonl` on this PC.

Inspect generated code without running it:

```powershell
python -m pyforge review --results results/qwen-1.5b-baseline.jsonl --output results/qwen-1.5b-static-review.jsonl
```

This uses `ast.parse` and checks for explicitly requested top-level names. Parsing and name presence are narrow static checks and do not establish functional correctness.

## Status and next stage

Revised Stage 0 is mostly implemented. Revised Stage 1 has a working local chat slice; a browser-level owner walkthrough, explicit cancel control and an internet-disconnected trial remain open. The earlier 20-task evaluation is only a Stage 3 prototype, not a validated benchmark lab. See the [implementation ledger](PYFORGE_AI_CODEX_REVISED_MASTER_PLAN.MD), [roadmap](docs/roadmap.md) and [current experiment log](docs/experiment_log.md). Stage 2 isolated execution is not implemented, so Run Tests remains disabled.
