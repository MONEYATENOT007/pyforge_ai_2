# PyForge AI — Revised Master Build Plan for Codex

**Version:** 0.2 — 2026-11-08  
**Purpose:** A build-ready specification for an **offline, consumer-PC Python coding assistant and model development laboratory**.  
**Status:** Target specification; verified implementation status is recorded in Section 12 below.  
**Supersedes:** Earlier PyForge briefs wherever the development order conflicts. Preserve good prior requirements (offline operation, safe execution, repository intelligence), but **the chat playground and measurable evaluation come before fine-tuning and multi-agent specialization**.

---

## 0. Primary instruction to Codex — implement, don't just summarize

You are implementing PyForge AI as a maintainable, GitHub-ready project. Read this document fully. **Start with Stage 0 (environment and storage preflight), then Stage 1 (working local chat UI), then Stage 2 (safe code testing).** Write real code, tests, requirements, documentation, and launch scripts. Deliver incremental working vertical slices. Do not attempt all stages in one large speculative implementation.

**In each stage:** (a) state the concrete design decision and why; (b) implement; (c) run applicable checks; (d) show evidence of what passed or failed; (e) explain constraints in beginner-friendly language; (f) stop at gates that need hardware information, model downloads, permission or deployment configuration. Never claim a test passed unless it actually ran.

**Owner is learning how SLMs, inference, agents, fine-tuning, testing, quantization, retrieval, and model routing work.** Add brief, meaningful technical explanations in the README and progress summaries. Avoid vague statements like “the AI learned” without controlled evaluations.

### Non-negotiable product requirements

1. **Fully offline everyday usage:** inference, routing, chat history, testing, repository search, debugging, and UI function without internet, hosted LLM APIs, API keys, or token billing. Network may be needed once to install packages or download weights. Bind local services to `127.0.0.1` by default; optional update/download flows require deliberate consent.
2. **Hardware-aware:** owner currently has AMD Ryzen 5 3600 (6C/12T), 16 GB DDR4 (2x8 GB; speed unverified), NVIDIA RTX 2060 6 GB VRAM. Windows is likely but **detect/confirm OS**. Several drives have approximately **200 GB free EACH**; enumerate actual drives, filesystem types, rotational/SSD if available, and free space before assigning directories.
3. **Don't assume five separate full models:** initially ONE shared coding foundation and FIVE role profiles; train specialist adapters only when evaluations justify it. Execute specialists sequentially to stay within RAM/VRAM.
4. **User-visible chat and manual testing come early:** the owner must be able to prompt “sort a list,” “explain this code,” or “fix this traceback” and inspect output. The testing laboratory is not a later optional dashboard.
5. **Security:** generated code is untrusted. Do not run it unsandboxed on the host. If an isolated Docker/container execution backend isn't installed/configured, disable execution and expose analysis-only feedback. No unreviewed host shell access. For production-grade isolation, prefer hardened isolation; ordinary Docker is a bounded MVP mechanism, not a perfect security boundary.
6. **Reproducible tests:** deterministic benchmarks where possible, prompt/version metadata, dataset provenance, held-out splits, pinned dependencies, and recorded memory/latency. Human feedback and model outputs are **candidates**, not automatically validated training data.
7. **Explicit approvals:** before large model downloads, changes to global Windows settings, drive moves, installing Docker/WSL/CUDA, training runs, writing outside approved workspaces, or destructive operations. Use non-destructive defaults.
8. **Never fabricate offline results:** offer a clear setup blocker when model, Docker, drivers, or GPU access are absent.

---

## 1. Product vision

Create an offline **Python-focused coding assistant** that is accessible on ordinary hardware. The initial product has two first-class experiences:

### A. Chat Playground (end user)
- ChatGPT-like message layout, session history, streaming answers, multiline prompts, Markdown/code formatting and copy controls.
- Ask the model to generate code, analyze pasted code, explain Python concepts, diagnose errors, suggest improvements, and later inspect an approved repository.
- Select model version and task role, see whether Ollama is connected, view current context limit, inference speed and approximate model memory usage where available.
- Provide thumbs up/down plus optional written comments and a “flag failure” action. Explicit opt-in to save examples for future dataset curation.
- **Run tests** or **request a repair** from the chat only once a correctly isolated execution backend is available.
- “Offline status” must be honest: local model ≠ necessarily 100% GPU; inference may offload to CPU.

### B. Model Laboratory (developer/researcher)
- Browse a curated problem bank and select domain + difficulty + skill (generation/explanation/debugging/refactoring).
- Run a single problem or bounded batch through a selected model profile; display pass/fail/timeout/error, logs, elapsed time, generation throughput, memory estimates.
- Compare **base** versus **fine-tuned candidate** fairly with equal prompts, context, inference parameters, test suites and execution environments.
- Inspect failed tasks, save feedback, export reports, build curated training candidate queues (not auto-train).
- Track training experiments later: dataset hash, base model revision, adapter version, hyperparameters, environment, held-out scores and regressions.

### Why this order matters
We should **build an environment that measures coding capability before trying to improve the weights**. A pretrained Qwen Coder model already knows how to sort lists. Correct answers to familiar tasks do not prove new learning. Train only after we have a credible baseline and unseen evaluation tasks.

---

## 2. Hardware and local resource allocation

### Hardware constraints
- **CPU:** Ryzen 5 3600, 6 cores / 12 threads.
- **GPU:** RTX 2060, 6 GB VRAM (constrains size and context; no guarantee 7B is fully GPU-resident).
- **RAM:** 16 GB DDR4 (OS + runtime + CPU offloading + browser all compete for this).
- **Disk:** several drives with approximately 200 GB available **per drive**, subject to preflight; exact letters/count/SSD-vs-HDD are **unknown**. Do not assume an earlier description of one 80 GB C: drive is still current.

### Model selection: provisional, subject to benchmarks
- **Coding quality baseline:** `qwen2.5-coder:7b` in Ollama, ~4.7 GB 4-bit quantized weights. Test an initial context around 4,096 tokens. It **may partially offload to RAM** and be slow on 6 GB VRAM.
- **Lightweight baseline / fallback:** `qwen2.5-coder:1.5b`, ~1 GB quantized in Ollama. Smaller, generally faster and easier to fine-tune, but lower ability on complex code and multi-step debugging.
- Optional middle ground: evaluate an appropriately licensed ~3B coding model only after confirming license, format, and actual GPU memory requirements. **Do not assume Qwen2.5-Coder-3B has the same license as 7B.**
- **No permanent commitment without evidence.** Benchmark correctness, latency, RAM, VRAM, context and tool-use behavior. Choose a default model based on balanced quality/speed rather than parameter count alone.
- Use **Ollama** first for ease of local integration via localhost; consider llama.cpp later if tighter quantization/offloading tuning is needed. Model selection, inference runtime and adapter training framework are separate concerns.
- 7B as **inference baseline** does **not** mean 7B QLoRA training will fit 6 GB VRAM. First training experiments should use a smaller compatible model and proven configuration.

### Storage layout policy (do not hardcode letters)
Build a storage preflight tool that enumerates mounted fixed volumes and free space using `psutil` / OS commands. Identify preferred fastest SSD/NVMe, secondary SSD (if any), and HDD. Show suggested mappings, require user approval, and persist paths in `config/storage.yaml` or equivalent.

**Allocation guidelines, each subject to free-space checks:**

| Storage tier | Suggested initial budget | Files | Rationale |
|---|---:|---|---|
| Fastest SSD / NVMe | **15–30 GB** | app source, Python venv, active model if capacity permits, active DB/index and UI assets | fast random reads/startups |
| Secondary SSD (if present) | **20–50 GB** | active evaluation artifacts, embeddings, temporary training scratch | reduce pressure on system drive |
| HDD or largest spacious drive | **40–100 GB initially** | source datasets, model archives, checkpoints, benchmark outputs, logs | capacity over speed |
| Unallocated free space | **Leave at least ~40–60 GB free on the system drive** where feasible, and reserve free space on other drives | OS, swap, updates and unexpected model files | reduce risk of filling disks |

Budget amounts are **caps/planning ranges, not reservations, quotas, or expected initial usage**. On a PC where each drive has ~200 GB free, keeping all model caches off the system drive may still be sensible; let owner choose.

Proposed configurable project roots (placeholders only):

```text
${FAST_ROOT}/PyForgeAI/
    app/                 # source, Streamlit UI, tests, virtual env optionally
    active_models/       # only if approved; otherwise Ollama-managed folder
    index/               # compact SQLite/code indexes
${DATA_ROOT}/PyForgeAI/
    datasets/
    model_archives/
    adapters/
    checkpoints/
    benchmark_runs/
    experiments/
    logs/
```

**Important operational details:**
- `OLLAMA_MODELS` must be set in the appropriate process/user environment **before Ollama starts** if directing model storage elsewhere. Confirm where the model actually landed. Do not silently move an existing Ollama folder.
- Also consider Hugging Face caches (`HF_HOME`, `HF_HUB_CACHE`), PyTorch/transformers caches, temporary files and Docker images; configure selectively and explicitly with user approval.
- Initial tasks should require substantially less than the reserved capacity. Do not create dummy multi-GB placeholder files.
- Never put active inference models on a slow HDD by default when SSD space comfortably allows it; HDD model loading can be slower. A model may be loaded into memory after startup.
- Avoid filling system drive or silently writing large training checkpoints; check space before every long job.
- Benchmark size estimates exclude inference KV cache and buffers; monitor VRAM using `nvidia-smi` and Ollama residency using `ollama ps` if installed.

---

## 3. Five Python specialist areas — curriculum and roles

**These are competence profiles, NOT rigid, equal-sized partitions of a software application.** One project may use all five. A small local model may play each role sequentially before separate adapters exist.

Suggested **development order**, which is a practical curriculum—not a universal claim about intrinsic difficulty:

| Order | Profile | Scope | Expected progression |
|---|---|---|---|
| 1 | **Core Python** | syntax, functions, list/dict/set, string processing, OOP, algorithms, exceptions, testing, refactoring | foundations to difficult debugging |
| 2 | **Automation & Scripting** | file I/O, OS operations, CSV/JSON, CLI, logging, schedulers, serial/device code | simple tools to robust pipelines |
| 3 | **Backend Development** | FastAPI, Flask, REST, Pydantic, DB/SQL, auth concepts, async, testing | endpoints to full services |
| 4 | **Desktop UI/UX** | **Tkinter** for minimal apps; **PyQt6** for richer applications; Qt layout, signals/slots, threads, accessibility, usability, responsiveness | simple windows to multi-screen desktop software |
| 5 | **AI / ML / Data** | NumPy, pandas, scikit-learn, PyTorch, retrieval, vector search, LangGraph / agentic tooling | data transformations to ML systems |

Across **every** domain, support six difficulty levels:
1. **L1 Fundamentals:** simple syntax, inputs/outputs, basic comprehension.
2. **L2 Problem solving:** functions, constraints, edge cases, multi-step logic.
3. **L3 Debugging:** tracebacks, logical failures, error explanations and fixes.
4. **L4 Design:** OOP, modules, dependency boundaries, tests and tradeoffs.
5. **L5 Application:** multiple files, services, framework integration and regressions.
6. **L6 Autonomous engineering:** repository-level diagnosis, complex constraints, performance, refactoring and system integration.

Also track a task-type axis: `generate`, `explain`, `debug`, `test`, `refactor`, `design`. Do not confuse domain difficulty with L1–L6. A simple Tkinter window can be L1, an intricate Core Python concurrency bug can be L6.

---

## 4. Architectural correction: component-first decomposition with five workers

For mixed-domain apps, **first identify cohesive software components**, then assign each component to its most suitable specialist. **Do not mechanically split every app into exactly five files/frontiers.** A project may need 2, 7, or 20 components; it still has five specialist *types*.

### Roles
- **Project architect / planner:** locally run model + deterministic checks; optional external ChatGPT-generated specification for development experiments only. Core operation must stay offline.
- **Shared contracts:** Pydantic schemas, method signatures, data formats, exceptions, dependency versions, concurrency rules, public APIs and test fixtures created *before* independent tasks.
- **Specialist executor:** one chosen role owns approved files and receives a narrow task packet.
- **Integration/debug coordinator:** runs unit, contract, integration, and regression tests; routes cross-component failures; escalates contract changes for review.
- **Repository intelligence engine:** later supplies symbol maps, imports, call edges, relevant code snippets and task-focused context.

### Task packets / component ownership
Each specialist task must declare: purpose, file ownership, input/output contracts, allowed dependencies, interfaces consumed, constraints, relevant snippets, acceptance tests and when to ask the coordinator for a change. Specialists should **not silently edit another owner's files**; they may request a cross-component contract change.

Example: a sensor monitor might have components for sensor parsing (Core), serial acquisition (Automation), REST + database (Backend), dashboard (UI), anomaly detection (AI), and startup/integration (Coordinator). Model profile selection should be based on each component, not simply detecting a library name in a shared file.

### Why the original idea was risky
Five separately fine-tuned models are not automatically faster or more accurate. The context is narrower, but scheduling, model swaps, incompatible interfaces, and integration debugging may cost more than using one shared model. **Measure three candidate architectures** later:
- **A:** single model handles the project using retrieval;
- **B:** single shared model plays five task roles with contracts and separate prompts;
- **C:** shared model + five specialist adapters, switched sequentially.

Only select C if held-out end-to-end quality improves enough to justify added complexity. On 6 GB VRAM, don't preload five 7B models.

---

## 5. High-level implementation architecture

```text
Local Streamlit UI (Chat Playground + Model Laboratory)
         |
         v
Python application/service layer
  |-- conversation manager (SQLite)
  |-- model runtime adapter (Ollama localhost)
  |-- prompt templates / task profiles
  |-- manual feedback store (SQLite)
  |-- benchmark runner + reports
  |-- sandbox execution service (isolated, opt-in)
  |-- debugging loop (bounded, evidence-based)
  |-- repository scanner / retrieval (incrementally)
  |-- component planner + contract validation (later)
  |-- adapter selection + training experiment metadata (later)
         |
         v
One active local coding model at a time (RTX 2060 / RAM)
```

Prefer a small, explicit Python codebase. Use **Streamlit** for initial UI (local web app), SQLite for conversations/metadata, Ollama's localhost API for inference, pytest for tests, Ruff for linting, `ast` for Python analysis, `psutil` for resource reporting, Git for change control, and Docker or equivalently hardened isolated execution for untrusted code. LangGraph may be adopted later if state-machine complexity justifies it. Do not require FastAPI in Stage 1 unless a clean boundary makes it useful.

Suggested repo layout (adjust if implementation proves simpler):

```text
pyforge-ai/
  README.md
  pyproject.toml
  .env.example
  .gitignore
  config/
    settings.example.yaml
    storage.example.yaml
  src/pyforge/
    ui/                # streamlit pages / components
    inference/         # runtime client, streaming, model registry
    chat/              # history, prompt assembly, persistence
    benchmark/         # tasks, validators, runner, scorecards
    sandbox/           # isolated execution interface
    feedback/          # ratings, comments, candidate queue
    repository/        # AST index, search, context builder
    agent/             # patch/retry workflows
    specialists/       # role definitions, task packets, contracts
    training/          # experimental pipeline, later
    system/            # hardware/drive preflight and metrics
  tests/
    unit/
    integration/
    fixtures/
  benchmark_data/
    public_examples/
    heldout/           # do not commit private hidden solutions
  scripts/
  docs/
    decisions/
    experiments/
```

Keep sensitive data, checkpoints, virtual environments, large datasets and cache directories out of Git. Do not commit hardcoded user directories.

---

## 6. Development stages and acceptance gates

### Stage 0 — Preflight and local inference integration
**Implement now.**
- Detect OS, CPU, RAM, NVIDIA GPU/VRAM/driver (when tools available), drives, free space; write a human-readable report.
- Propose storage roots based on SSD speed, free space and explicit user choice. Never move existing directories without permission.
- Check Python, Git, Ollama and optional Docker availability; avoid silently installing system packages.
- Add a local Ollama client abstraction with robust errors for server not running, model not downloaded, context limits and stream interruptions.
- Configuration: Ollama endpoint restricted to localhost, model name, context length, generation parameters, data paths, execution off by default.
- Provide commands for owner to approve/install/pull `qwen2.5-coder:7b` and `qwen2.5-coder:1.5b`; downloads are user-authorized, not automatic.
- Report actual model residency and VRAM using available tools, not hardcoded promises.

**Exit:** app can connect to a local Ollama model *when installed*; no unapproved network/cloud call, environment report created, disk choices recorded, and missing prerequisites clearly flagged.

### Stage 1 — Chat Playground MVP (TOP PRIORITY)
**Implement immediately after Stage 0.**
- Streamlit app with chat messages, Markdown + Python syntax-highlighted fenced blocks, streaming responses, multiline prompt entry, loading/cancel states where viable.
- SQLite persistent conversation sessions (create, list, rename/delete with confirmation), timestamps, model name, settings and export to JSON/Markdown.
- Select installed local model; separate role selector (`General`, `Core`, `Automation`, `Backend`, `UI/UX`, `AI/Data`) initially changes system instructions only, **not** model weights.
- User feedback: thumbs up/down, free-text correction, saved candidate flag (off by default).
- Basic metrics shown when available: time-to-first-token, generation duration, tokens/s, model, parameters, context, whether inference server is available.
- Handle unavailable Ollama/model gracefully. Prevent accidental remote API use.
- Minimal usable UI that resembles modern chat, not a fake visual mockup. Do not over-engineer frontend.

**Exit:** on the owner's machine, a user can disconnect internet, open local Streamlit chat, ask “write a function to sort a list,” obtain a streamed response, save conversation, and submit feedback. If a model cannot be executed in Codex's environment, automated tests for mocked inference still pass and the real-device check is documented as pending.

### Stage 2 — Execution/Test Lab embedded in Chat
- Add a **separate isolated execution backend** with resource quotas, timeouts, no network, bounded output, read-only source mounts by default, ephemeral writable workspace, non-root process, and no host secrets. Docker may implement an MVP backend only if configured appropriately; do not imply it is fully secure against malicious code. Never mount Docker socket into test container.
- A generated snippet is **not executed automatically**. The user reviews code and clicks `Run tests`. For larger edits, show diffs and require approval.
- Build curated benchmark fixtures beginning with list sorting, duplicate handling, second-largest distinct number, string transformations, OOP and exception handling.
- For each candidate solution: parse/extract code, syntax check, run limited test suite, capture stdout/stderr, status, resource/time metrics.
- Check both output and *constraints*, e.g. prohibition on `sorted()`/`.sort()`, no mutation of input, correct exception behavior, no external libraries. Some constraints may need AST analysis and tests.
- Distinguish failures: `syntax_error`, `wrong_answer`, `constraint_violation`, `runtime_error`, `timeout`, `sandbox_unavailable`, `not_testable`.
- Tests passing ≠ guaranteed correctness. For ordinary chat responses that aren't self-contained code, show `Not automatically tested` rather than a fabricated green check.

**Exit:** user can generate sorting code in chat and inspect real, isolated test results and diagnostic messages. Without a sandbox, execution UI remains disabled, analysis-only mode works.

### Stage 3 — Benchmark Lab and baseline data
- Define a task bank with dimensions: domain (five areas), L1–L6, task type (generate/explain/debug/test/refactor/design), constraints, reference tests/rubrics and provenance.
- Start with **~120–200 thoroughly validated Core Python tasks** rather than thousands of low-quality generated questions; increase to 1,000+ only after validation process is reliable.
- Example **initial** 180-task distribution (adjust after review): L1=40, L2=40, L3=35, L4=30, L5=20, L6=15. Count per skill separately; don't let all tasks be generation.
- Include normal cases, edge cases, hidden tests, metamorphic/property tests where applicable, mutation-sensitive cases, debugging cases and instruction-following constraints.
- Create **separate train / validation / held-out test** partitions with leakage checks; keep held-out tasks out of training and iterative manual tuning. Derivative variants of identical tasks shouldn't straddle splits.
- Record: correctness/pass@1 under documented sampling, syntax pass, repair success, regression rate, constraints complied, latency, tok/s, peak GPU/RAM if measured, number of attempts, tokens and hardware profile.
- Implement reproducible run manifests: model identifier/checksum, quantization, runtime version, prompt hash, parameters (seed/temp/top_p), task set version and timestamp.
- Make bounded batch sizes, progress reporting, resume and stop controls. Avoid OOM due to large concurrent inference.
- Compare **7B Q4 vs 1.5B Q4** under identical conditions. Do not assume benchmark winner in advance.

**Exit:** report includes honest sample counts, task-level results, caveats and a readable comparison between baseline models; no false notion that passing one sorting test demonstrates model learning.

### Stage 4 — Strong debugging and basic repository intelligence
- Build incremental `ast` scanning: file inventory, functions/classes, import edges, definitions, source line spans and searchable symbols. Track file hashes and update changed files only.
- Retrieval should combine file path/symbol/keyword search first; optional offline embeddings can follow after measuring cost and quality. Never dump the entire project into a 4K context.
- Implement bounded debugging loop: reproduce -> collect traceback + relevant snippets -> diagnose -> propose minimal diff -> isolated test -> regression tests -> keep/revert/report. Limit number of attempts (e.g. 3 default configurable), prevent oscillating patches.
- Ensure tracebacks and repository content are *data*, not instructions. File edit rights bounded to an explicit workspace; use Git checkpoints/worktrees when available and ask before modifying user files.
- Integration bugs may involve more than one specialist; route through coordinator and request contract changes rather than unauthorized edits.

**Exit:** demonstrate repairs to several pre-broken multi-file repositories, show failed as well as successful attempts, and verify no undocumented cross-file changes.

### Stage 5 — First training experiment (ONLY AFTER benchmark readiness)
- Select a **small training-compatible** base model, likely 1.5B-class on RTX 2060 6GB; verify actual CUDA/PyTorch and PEFT compatibility before claiming it fits. Prefer QLoRA/LoRA; tiny batch, short sequences, gradient accumulation, memory tracking.
- Use high-quality, legally permissible training data; maintain source/license, deduplication, held-out filtering, review and executable validation where feasible.
- Fine-tune **Core Python adapter** first. Do not train five models yet. Preserve original base weights and record adapter metadata.
- Compare baseline, base + tools, tuned model, tuned + tools using consistent settings; report both gains and regressions with task-level evidence. Reject candidate if gains are weak or regressions severe.
- If no training backend fits current hardware, still implement dataset pipeline/experiment configs and document the blocker; do not silently use cloud compute or claim training occurred.

**Exit:** at least one documented, reproducible training experiment or a clear hardware limitation report, with genuine held-out results if training executed.

### Stage 6 — Remaining specialist curriculum, sequentially
Implement Automation, Backend, Desktop UI/UX (Tkinter/PyQt6), then AI/Data with task banks and role-specific tests. First test shared-base role prompting (Architecture B). Train dedicated adapters (Architecture C) **only if** the shared model measurably underperforms on targeted tasks and training data is available. Keep one active model at a time.

### Stage 7 — Contract-driven application builder
Given a mixed-domain requirement, decompose into cohesive components; generate an ownership/dependency graph, shared Pydantic contracts, schemas, public APIs, and acceptance criteria. Assign components to specialists. Test unit, contract, integration and regression behavior. Evaluate Architecture A vs B vs C on the **same** projects, hardware budget and metrics. Offline planner is required; an optional externally authored ChatGPT architecture can be imported as a specification, but not a runtime dependency.

### Stage 8 — Advanced large-repository analysis, modularization and UI verification
Expand indexing to callers/references (best effort for dynamic Python), hierarchical summaries, retrieval relevance evaluations, context-budget management, Git-aware refactoring, safe module extraction and migration. For PyQt6/Tkinter, add headless widget tests and optionally locally captured screenshots/visual review; UI must not freeze due to long work on main thread. Avoid asserting correctness from a screenshot alone.

### Stage 9 — Python specialization and compression research (OPTIONAL)
Evaluate teacher (7B) -> smaller student (e.g. 1.5B) via **verified Python-specific instruction data / distillation**, and later structured pruning or tokenizer/vocabulary research if resources justify it. Fine-tuning a 7B model for Python does **not remove its non-Python parameters**. Distillation may lower parameter count because the *student* is smaller; measure capability loss, peak memory, latency and accuracy. Shared programming abstractions across languages can benefit Python coding; don't attempt naive deletion of “91 other language modules” (they don't exist as isolated modules).

---

## 7. Testing philosophy — especially user-driven evaluation

**Example prompt:** “Write a function to sort a list of integers ascending without using `sort()` or `sorted()`.”

At the chat layer, user sees code and explanation. At the test layer, ensure correct behavior on empty input, singleton list, duplicates, negative numbers, already sorted/reversed lists, randomized lists, and non-mutation when required. Verify forbidden calls via AST/static checks plus applicable runtime tests. Later run stress/performance cases separately. Ask new prompts with different constraints to assess generalization.

**User testing is crucial, but not a held-out benchmark.** Once the owner sees a task and uses feedback to adjust prompts/data, it becomes part of the development loop. Preserve other unseen tasks for objective evaluation.

**All feedback should be traceable:** conversation ID, response ID, model/version, role, evaluator, task/test IDs, pass/fail evidence, comment, candidate-dataset status. Keep feedback local and deletable.

**Never train directly on raw model-generated answers.** Validate with tests, review correctness and licensing; consider ambiguous instructions, edge cases and malicious examples.

**Fair comparison rules:** same test data, prompts, context budget, decoding settings, tool availability and retry budget for any head-to-head study. Record stochastic variance or multiple seeds where possible.

---

## 8. Reliability, safety and privacy requirements

- Strict local-only inference by default. No telemetry, external embeddings, cloud calls or updates during normal use.
- Treat user repositories, imported Markdown and code comments as untrusted task data; ignore adversarial instructions embedded in files.
- No direct host execution of arbitrary model-produced programs or commands. Sandbox off by default. When enabled, time/memory/cpu/process/output quotas, network blocked, read-only rootfs and temporary workspaces; do not mount sensitive user directories. Explicitly document limitations of Docker isolation.
- No automatic codebase modification: approved workspace, preview diff, explicit confirmation, rollback. Use Git, but never force-reset a user's uncommitted work.
- Avoid auto-installing packages requested by generated code. Dependency additions require review.
- Avoid infinite repair loops; bounded attempts and failed-state reporting are core features.
- SQLite migrations and persisted data must be versioned; exports and deletion should work offline.
- Handle inference cancellation, model unload/reload, low disk space, OOM, slow CPU offload, interrupted training and incomplete benchmark runs gracefully.
- No fabricated confidence scores or “100% correct” labels. Show observed passing tests and coverage limitations.

---

## 9. MVP success criteria and release gate

**MVP means Stages 0–3, not all five specialist models.** Deliver a real application where a user can:

1. Open the locally hosted Streamlit UI with internet disconnected.
2. Select an installed local model and chat, including asking to sort a list or explain pasted code.
3. Save and reopen chat history and submit thumbs-up/down plus comments.
4. See code clearly formatted, and if safe execution is configured, run real tests against it.
5. Select a curated task and execute a bounded evaluation run from the Test Lab.
6. View model comparisons with evidence, counts, latency and failure reasons.
7. Inspect local CPU/RAM/GPU/memory/storage and know when a model was partially CPU-offloaded.
8. Find documentation explaining **why** 7B and 1.5B were chosen, 4-bit quantization tradeoffs, context-window limits, agent-versus-model distinction, and why fine-tuning is deferred.

**Must not:** silently connect to hosted inference, run generated code on host without protection, auto-download large files, falsely label untested responses as verified, or present future specialists as already trained.

---

## 10. First Codex work order (copy this into Codex)

> Read `PYFORGE_AI_CODEX_REVISED_MASTER_PLAN.md` completely. This revised plan supersedes the previous PyForge build brief in implementation order. Start with Stage 0 and Stage 1 only. Inspect my Windows/Linux environment, Ryzen 5 3600, RTX 2060 6GB, 16GB RAM, and multiple drives with around 200GB free each. Report real drives and propose resource allocation before any downloads or system changes. Build a working, modular Streamlit chat playground backed by a local Ollama model, with session persistence, model selector, streaming, feedback, offline/error handling and tests using a mock inference client. Explain key technical decisions and do not say unrun tests passed. Provide exact startup instructions and a list of prerequisites requiring my approval. Do NOT begin fine-tuning or build five full models. Leave generated-code execution disabled until an isolated execution backend is implemented and verified.

---

## 11. Expected first-stage deliverables

- `README.md`: setup, offline architecture, limitations, step-by-step run instructions and learning notes.
- `pyproject.toml` / pinned dependency policy and reproducible install instructions.
- Local Streamlit chat app with a typed internal boundary where useful but readable Python code (avoid unnecessary complexity).
- Ollama runtime client with streaming support, model listing, errors, and mock/test substitutes.
- SQLite conversation and feedback persistence plus basic local data export.
- Hardware/disk preflight script and proposed config file, requiring approval for changes.
- Unit tests for model adapter, chat persistence, config validation and feedback workflow.
- `docs/decisions/0001-model-selection.md` documenting model pros/cons, licensing checks, 6GB VRAM limits, and measurable selection criteria.
- `docs/roadmap.md` with Stage 2 onward, and `docs/experiment-log.md` tracking what actually happened.

**End of target specification; implementation ledger follows.**

---

## 12. Implementation ledger — 2026-11-08

This ledger records observed work in this repository; the specification above remains the target. Earlier Phase 0/1 work maps partly to revised Stage 0 and partly to an early Stage 3 evaluation prototype. **A 20-prompt baseline does not complete the revised Stage 3 task bank.**

| Revised stage | Status | Evidence completed | Still open |
|---|---|---|---|
| Stage 0 — preflight and inference | Mostly implemented | Windows doctor reports drives, CPU/RAM, NVIDIA GPU/VRAM and driver, Python/Git/Ollama/Docker availability; portable Ollama 0.40.14 and Qwen2.5-Coder 1.5B Q4_K_M on approved F:; localhost-only client, model listing, streaming and interruption errors; F: model location and cloud-disabled server verified | Physical media type for non-C drives and permanent storage-root config deferred by owner; 7B not downloaded or measured |
| Stage 1 — chat playground | In progress, working local slice | Streamlit chat page, model and role selectors, bounded history prompt, streamed answers, SQLite session history with versioned schema, rename/delete confirmation, JSON/Markdown exports, ratings/comments and opt-in candidate flag; local launch script; mocked UI flow and real model streaming tested | Browser interaction by owner, explicit cancel control, dedicated failure flag, full offline-disconnected check and UI polish remain unverified |
| Stage 2 — isolated execution | Not started | Generated code is never run by chat or benchmark; static AST review is analysis-only | Isolated runner and test lab |
| Stage 3 — benchmark laboratory | Prototype only | 20 fixed prompts, raw outputs, token/latency/resource snapshots, three 1.5B runs, manual error review | Validated 120–200-task bank, train/validation/held-out splits, executable grading, 7B comparison and reproducible manifests |
| Stages 4–9 | Not started | No repository agent, fine-tuning, trained specialists or autonomous patching claimed | Follow the revised order after MVP gates |

Verification already run: 22 prior unit/integration tests passed before the revised plan; the expanded suite reached **33 passing tests** including Streamlit AppTest smoke and mocked send/feedback flow. The local streamed model call saved a completed SQLite record; Streamlit served HTTP 200 on `127.0.0.1:8501`. See `PHASE0_REPORT.md`, `PHASE1_REPORT.md` and `docs/experiment-log.md` for measured details. A browser-level user walkthrough and internet-disconnected trial have not been claimed.

## 13. First user test update — 2026-11-08

The two outputs in `FIRST_TEST_RUN_BY_USER.md` are user-observed baseline examples, not executable test results. Stage 1 now has schema-v3 UUID sessions/messages, editable response-linked feedback with failure category, run-configuration fields, and selected-session Markdown/JSON export with default-on redaction and JSON import validation. Stage 3 now has a static requirement checklist for the reported sorting and Tkinter prompts plus an evaluation-case queue that snapshots the exact chat prompt and response. These are implemented source features; no runtime correctness claim is attached to either user example.

The full test suite reached 41 passing tests during this update; see `docs/experiment_log.md` for the final verification record. Stage 2 remains open: the Run Tests control is disabled until isolated execution with disposable files exists. No paired model re-test, GUI execution, browser walkthrough, or fine-tuning has been completed.

## 14. Local version and progress ledger — 2026-11-08

PyForge package version 0.2.0 is now sourced from `pyforge/_version.py` and shown by the CLI and chat UI. The root `progress.md` is the current implementation ledger across this revised plan, the original build brief and the first user test report. The versioning change passed 42 tests, and local installed metadata matched 0.2.0. See `docs/experiment_log.md` for the command evidence.

## 15. Session 02 analysis update — 2026-11-08

Version 0.3.0 adds a redacted five-response static fixture from the user's actual session, context-aware requirement checks, pre-generation GUI checklists, visible static warnings, response-linked problem reports and best-effort model provenance from Ollama's local tags/version endpoints. A two-case 1.5B prompt probe still failed static renamer and dashboard criteria. Generated code was not executed; Stage 2 isolation, verified repair and a fair 7B comparison remain open. See `progress.md` and `docs/experiment_log.md` for precise evidence and limits.
