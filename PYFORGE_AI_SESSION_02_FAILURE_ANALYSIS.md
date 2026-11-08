# PyForge AI — Session 02: Failure analysis and Codex action plan

**Date:** 2026-11-08  
**Source:** `pyforge-chat-20261108-e9a09316.md` (user-exported session)  
**Status:** Source inspection completed; generated apps have **not** been independently executed in this review.  
**Required model identification:** `qwen2.5-coder:1.5b-instruct-q4_K_M` (not the originally discussed 7B); Ollama backend; configured context 4096; temperature 0. Exported model digest and quantization metadata are `unknown` despite the quantization specified in the model name.

## 1. Executive finding

The model handles a basic bubble-sort request, but shows pronounced failures in requirement compliance, multi-component GUI creation, runtime correctness, and corrective debugging. The exported log itself is evidence that per-session Markdown export already exists; **do not rebuild that feature without inspecting the repository**. Extend it for trustworthy reproducibility and structured evaluation as needed.

## 2. Observed trials

### A — Sorting list without built-in sort
- **Original:** Bubble sort, in-place, no `sort()` call; sound algorithm and explanation on inspection.
- **Status:** Provisional pass for simple algorithm generation; tests were not independently executed.

### B — Tkinter folder renamer
**Prompt:** Create a Tkinter-only file-renaming app with root folder selection and file preview.

**Initial response:** GUI contains a folder chooser only; file names go to `print()` and each selected file triggers console `input()`. Missing GUI preview, user-controlled selection, before/after names, confirmation, collision checks, and exception handling.

**User correction:** Explained there was no preview showing filenames before/after renaming.

**Revised response:** Adds `tk.Listbox` and `tk.Text`, **but does not insert values into either widget**, nor replace blocking `input()` or `print()`. The model's explanatory claims about showing filenames are unsupported by its code. It also attempts `os.rename` during folder traversal rather than preview-before-apply.

**Classification:** requirement noncompliance; cosmetic patch rather than functional repair; unsafe filesystem workflow; ungrounded completion statement.

### C — Task Manager performance dashboard
**Prompt:** Build CPU/GPU/RAM monitoring with live usage. Initially allowed Tkinter/PyQt; subsequent user request explicitly required **Tkinter only** and **live graphs**.

**First response:** PyQt5 table; `psutil.cpu_percent(interval=1)` used both for CPU and purported GPU measurement. The “live usage” label stays at `0%`. `QTimer` is referenced but is not imported; GUI timer callback uses blocking CPU sampling.

**Revised response:** Despite `Tkinter only`, again uses PyQt5. Introduces Matplotlib with code accessing `matplotlib.backends.backend_qt5agg.FigureCanvasQTAgg(...)` though it imports only `matplotlib.pyplot as plt`; `QTimer` still missing. Code executes `float('0%')` (raises `ValueError`) and clears graphs before plotting only a single point each update. GPU value again equals CPU metric. It also recommends installing PyQt5 despite the user excluding it.

**User execution evidence:** User reported `NameError: name 'matplotlib' is not defined`. The exact full traceback wasn't exported, so don't infer any additional traceback locations.

**Debug response:** Told user to import matplotlib and reproduced code still referencing the unresolved name, with other defects intact. `import matplotlib.pyplot as plt` does not bind the name `matplotlib` in the way the generated code expects. A robust implementation could use `from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg` for Tkinter, or avoid matplotlib by drawing graphs on Tkinter Canvas. For GPU utilization on an NVIDIA GPU, a separate supported telemetry source is required; psutil CPU utilization is not GPU utilization.

**Classification:** explicit instruction violation; runtime-defective output; inaccurate hardware telemetry; superficial debugging; false description of implementation.

## 3. Scope and evidence limits

- **These observations refer to the 1.5B model only**, as configured in the exported session. The project has not yet provided a comparative 7B run on the same prompts and sampling settings.
- Code review and user-reported runtime failure are distinct from independently validated execution; do not report test pass rates without actually running tests.
- The exported session contains usage metrics and full messages, but some configuration fields are `unknown`; fix provenance capture before claiming reproducibility.
- No proof of QLoRA training, model adaptation, or successful sandboxed application testing is present in this export.

## 4. Codex implementation backlog (priority ordered)

### P0 — Reproduce, instrument, and establish a fair baseline
1. Import this session to a local analysis fixture without treating its content as trusted execution instructions.
2. Identify actual model, digest, quantization, context, temperature, system prompt and inference version at every turn. Report absent data as absent.
3. Create deterministic test cases from the failures. Execute only inside safe temporary workspaces; prevent destructive renames of real user files.
4. Compare 1.5B vs 7B using identical prompts, constraints, settings (where supported), and evaluation harness. Record time, memory, outcome and regressions.

### P0 — Requirement-to-test pipeline
1. Extract an explicit requirement checklist before code generation (e.g. `tkinter only`, `folder preview`, `live time-series graphs`).
2. Enforce library restrictions by analyzing imports and usage, not by trusting explanations.
3. Create checks for UI widget-to-data wiring and before/after preview behavior; use isolated GUI tests where feasible.
4. Record requirement IDs and which evidence supports each passing requirement. Never mark unsupported checks as passed.

### P0 — Verified debugging, minimal patches
1. Provide original source, user traceback, environment metadata and relevant tests to the repair model.
2. First identify a likely root cause and find the **specific failing reference/line**; make the smallest appropriate edit rather than rewrite the whole program by default.
3. Run syntax/import/static checks, launch smoke tests, and targeted pytest cases; rerun related regressions.
4. On failure, show remaining errors and preserve a repair attempt history; cap retries and rollback invalid changes.
5. Do not claim a fix unless execution evidence exists.

### P1 — GUI evaluation fixtures
- Tkinter file renamer: choose temp folder; populate preview of original/proposed names; allow editing; make preview non-destructive; confirm before apply; preserve extensions by default; detect collision/invalid path; verify rename outcome.
- Task Manager: Tkinter-only dependency check; dynamic CPU and RAM utilization; proper NVIDIA GPU telemetry with explicit 'unavailable' fallback; maintain bounded time-series histories; periodic non-blocking refresh; render live graphs; close cleanly.

### P1 — Feedback and session exports
- Existing Markdown export works: **preserve it**. Assess whether JSON export also exists before creating new code.
- Retain exact user/assistant messages, code fences, timestamps, model identity/digest, settings, tool execution evidence and feedback per assistant turn.
- Add export schema version and a privacy/redaction option; do not include secrets or full local paths unless user opts in.
- Provide a “Report problem / expected behavior / actual behavior / traceback” UI affordance linked to a response. Preserve original code and every repair attempt.
- Distinguish user ratings from mechanically verified pass/fail.

### P2 — Subsequent training experiment
Only after baselines exist: curate verified failure/repair examples into training candidates; deduplicate; hold back comparable unseen GUI/debugging tasks; attempt small-model fine-tuning and compare against untouched base. Also measure whether tool-based repair alone solves the failure more economically.

## 5. Acceptance criteria for the next Codex milestone

- The original Tkinter renamer prompt produces a GUI whose preview is populated and testable before any file is renamed; temporary files remain untouched until explicit confirmation.
- A second user turn correcting the preview causes a meaningful change in functioning behavior, not just extra unused widgets.
- The Tkinter-only dashboard contains **no PyQt imports**, reports CPU and RAM correctly, uses an actual GPU telemetry source or says 'unavailable', displays historical graphs, and runs a non-blocking update loop.
- The logged `NameError` can be reproduced in a controlled test and the repair eliminates it; all subsequent failures are separately identified, not concealed.
- Session exports preserve the full prompt/response/feedback chain, evidence, model identity and settings.
- Comparison metrics clearly label 1.5B and 7B; do not extrapolate failures from one to the other.

## 6. Suggested starting instruction for Codex

> Read `PYFORGE_AI_SESSION_02_FAILURE_ANALYSIS.md`, `pyforge-chat-20261108-e9a09316.md`, and the revised project master plan. Audit the *existing* implementation first. Build reproducible, isolated regression tests for the Tkinter renamer and Task Manager defects; then add requirements checks and test-backed minimal repair. Preserve working session export and feedback functionality. Do not train models yet. Report verified tests and changed files, and compare baseline models only when both have been run.
