# PyForge AI progress

**Local package version:** 0.2.1 (source: `pyforge/_version.py`)

**Last updated:** 2026-11-08
**Status:** Working offline-first chat and analysis prototype. Isolated execution is not available.

This is the current work ledger. Update it in the same change as any source, test, configuration or documentation change. Record what changed, what was actually verified, what remains open, and the package version when it changes. Preserve prior evidence in the phase reports and [experiment log](docs/experiment_log.md); do not turn planned features into completed claims.

## Completed and verified

| Source plan | Implemented | Evidence |
|---|---|---|
| [Initial brief](PYFORGE_AI_CODEX_BUILD_BRIEF.md), Phase 0 / [revised plan](PYFORGE_AI_CODEX_REVISED_MASTER_PLAN.MD), Stage 0 | Python package, CLI, config example, read-only doctor, storage guidance, local Ollama adapter and approved model on F: | [Phase 0 report](PHASE0_REPORT.md); doctor and model tests |
| Initial Phase 1 / revised Stage 1 | CLI chat, Streamlit chat, model/profile selectors, streaming, sessions, feedback, deletion confirmation, offline loopback model API | [Phase 1 report](PHASE1_REPORT.md); Streamlit AppTest and local stream evidence |
| Initial Phase 1 / revised Stage 3 prototype | 20 fixed prompts, raw-output benchmark recorder, latency/token/resource snapshots, non-executing AST review | [Phase 1 report](PHASE1_REPORT.md); benchmark/static-review tests |
| [First user test report](FIRST_TEST_RUN_BY_USER.md), P0 | SQLite schema v3 with stable UUIDs and v1 migration; full selected-session JSON/Markdown export; default redaction and preview; JSON import; editable response-linked rating/comment/category | [First user test log](docs/experiment_log.md); export/import, migration, redaction and UI tests |
| First user test report, partial P1 | Static requirement checklist for the two reported prompts, analysis-only response queue, disabled Run Tests control | Tests compare the supplied outputs; no generated code was executed |
| Current versioning change | One package version source, CLI `--version`, UI version display and this ledger | CLI, package import and installed metadata all report 0.2.0; full suite passed 42 tests; `pip check` was clean |

The original Test 001 sorting response has **static evidence** for avoiding built-in sort; sorting correctness is unknown until isolated tests run. Test 002's supplied Tkinter code has static evidence of folder selection and static failures for in-GUI preview, in-GUI filename entry and confirmation. These are not GUI runtime results.

## Remaining work, in plan order

| Priority / stage | Next work | Current state |
|---|---|---|
| Revised Stage 1 | Owner browser walkthrough, explicit cancel control, offline-disconnected trial, UI polish and failure reporting | Open; Streamlit AppTest and HTTP health are not a browser walkthrough |
| First user test P0/P1 | Browser verification of export downloads/copy, direct evaluation-lab import UI, broader human-reviewed checklists | Open; JSON import API and queue exist |
| Revised Stage 2 / first user test P1 | Hardened isolated runner with no internet, bounded time/memory and disposable synthetic files; sorting matrix and Tkinter GUI acceptance fixtures | Not implemented; Run Tests stays disabled |
| Revised Stage 3 | Validated 120–200 task bank, held-out splits, reproducible manifests and genuine correctness grading; paired short/structured Test 002 model experiment | Prototype only; exact model/config for the user-supplied outputs is unknown |
| Revised Stages 4–9 / initial Phases 2–6 | Repository intelligence, controlled debugger/repair, modular changes, then evidence-gated training/specialists and advanced UX/research | Not started; no fine-tuning authorized or performed |

## Environment and boundaries

- Main project, environment, model and database are on F:. C: is the SSD and the owner capped its use for this project at 40 GB. G: is overflow if F: runs short.
- The existing F: chat database was backed up as `local_runtime/data/chat-pre-first-user-run-v1.sqlite3` before migration; one session and six messages were preserved.
- Generated code from users or models is never executed by the current chat or evaluation flow. Personal folders are not used as test fixtures; the supplied Markdown report is read only for static regression checks.
- `local_runtime/`, `results/`, environment files and local storage configuration are ignored by Git.

## Change record

| Date | Version | Change | Verification |
|---|---|---|---|
| 2026-11-08 | 0.1.0 | Initial preflight, local model, benchmark and working chat slices; see phase reports | Earlier suite reached 33 tests; see [implementation ledger](PYFORGE_AI_CODEX_REVISED_MASTER_PLAN.MD) |
| 2026-11-08 | 0.2.0 | First user test export, feedback and static evaluation work; centralized local version and progress tracking | 42 tests passed; installed metadata and CLI match 0.2.0; see [experiment log](docs/experiment_log.md) |
| 2026-11-08 | 0.2.1 | Put the version in the main chat header, enable automatic rerun on save and add a guarded restart script for stale/unavailable service | 42 tests passed after the launcher change; real database AppTest had zero exceptions and showed v0.2.1; live command line has `runOnSave=true` and port 8501 returned HTTP 200; see [experiment log](docs/experiment_log.md) |
