# PyForge AI — First Test Run by User

**Recorded:** 2026-11-08  
**Document type:** User-observed evaluation report and Codex change request  
**Project:** PyForge AI (offline Python coding assistant and model laboratory)  
**Model under evaluation:** User-reported local Qwen coding setup; **exact tag, quantization, settings, and generation logs were not supplied**. Earlier project plan proposes `qwen2.5-coder:7b`, but do **not** silently assume that is the executed version.  
**Execution status:** Responses were provided by the user. No automated tests, GUI runtime inspection, or environment telemetry are attached. All assessments below are based on static inspection, not measured runtime results.

## 1. Instructions to Codex

Read this document alongside `PYFORGE_AI_CODEX_REVISED_MASTER_PLAN.md`. Treat this as a **new implementation/evaluation requirement**, not a claim that any feature is already present. Prioritize (A) durable per-chat export, (B) trustworthy response feedback, (C) requirement-based evaluation, and (D) runnable regression tests. Do not initiate fine-tuning based on two examples. Implement incrementally; after each change, run relevant tests, report actual evidence, and distinguish implemented, proposed, and blocked functionality.

### Required new capabilities

1. **Export Chat Session:** One-click export of the currently selected chat session to self-contained Markdown and JSON (recommended both), with *complete prompts and model responses*, message ordering, timestamps, model/version/profile/configuration where available, and optional user ratings/comments. Do not truncate model code fences or explanations. Export should remain useful for pasting into ChatGPT and for direct import into the evaluation lab.
2. **Per-response user feedback:** Preserve the existing feedback request after each response (user confirms this behavior already exists). Ensure thumbs-up/down plus optional text reason, linked to the precise assistant message and model run; allow editing feedback; avoid repeated prompts after feedback is submitted.
3. **Requirement compliance evaluation:** Extract explicit user requirements and acceptance criteria into a checklist. Distinguish *asserted coverage*, *static evidence*, *runtime verified*, *failed*, and *unknown*. For desktop GUI apps, test that interactions are GUI-based rather than `input()`/terminal `print()` in callbacks. The checker should not misrepresent LLM self-criticism as proof of correctness.
4. **Test lab integration:** Route selected chat responses into evaluation cases; run isolated tests only if a safe execution backend is configured. File-management tests use temporary directories and synthetic files only; no access to personal folders.
5. **Versioned records:** Persist model identity, runtime, quantization, sampling settings, system prompt/profile, token/context configuration, benchmark/test-suite version, result, elapsed time, and optional GPU/RAM telemetry if available. Mark missing fields `unknown`, not invented.
6. **Prominent manual testing:** Keep the chat interface front-and-center, with an explicit `Run Tests` action when safe execution is available and `Export session` action that works even without a runner.

## 2. User Test 001 — Sort a list without Python's built-in sort

**User prompt (original wording):**

> wirte a code to sort a list of n elements without using sort function inbuilt in python

**Model response — code as supplied:**

```python
def bubble_sort(arr):
    n = len(arr)
    # Traverse through all array elements
    for i in range(n):
        # Last i elements are already in place
        for j in range(0, n-i-1):
            # Traverse the array from 0 to n-i-1
            # Swap if the element found is greater than the next element
            if arr[j] > arr[j+1]:
                arr[j], arr[j+1] = arr[j+1], arr[j]

# Example usage
arr = [64, 34, 25, 12, 22, 11, 90]
bubble_sort(arr)
print("Sorted array is:", arr)
```

**Model response — explanation as supplied (format normalized only):**

1. **Outer Loop (`for i in range(n)`)**: This loop runs `n` times, where `n` is the length of the array. It ensures that each element is moved to its correct position in the sorted portion of the array.
2. **Inner Loop (`for j in range(0, n-i-1)`)**: This loop runs from the start of the array up to the last unsorted element. It compares each element with its next neighbor and swaps them if they are in the wrong order.
3. **Swapping**: Inside the inner loop, if the current element is greater than the next element, the two elements are swapped using tuple unpacking.

**Model's example:** For `[64, 34, 25, 12, 22, 11, 90]`, output is `[11, 12, 22, 25, 34, 64, 90]`.

**Model's note:** Bubble sort is not the most efficient sorting algorithm for large datasets due to its high time complexity of `O(n^2)`, but is simple to understand and implement.

### Static assessment

- **Pass (by inspection):** valid Python syntax, ascending sort algorithm, no use of `list.sort()` or `sorted()`, explanation broadly correct.
- **Not a defect given prompt ambiguity:** sorts *in place* and returns `None`; original prompt does not mandate returning a copy. Should disclose mutation.
- **Quality limitations:** worst-case `O(n²)` time, no explicit automated tests, no discussion of empty/single-element/duplicate inputs; simple example only. Do not penalize the choice of bubble sort as noncompliance.
- **Result label:** `likely_correct_unexecuted`, **not** `runtime_passed`.

### Verification tasks for Codex

- Use a safe runner to check empty, one-element, duplicate, negative, pre-sorted, reverse-sorted and random lists; use Python's `sorted()` only as the **test oracle**, never inside the candidate implementation.
- Confirm mutation behavior explicitly and compare the exact expected result with the candidate's in-place mutation.
- Log latency, model configuration and output format. Test explanation accuracy separately from executable correctness.
- Avoid contaminating held-out benchmarks by reusing this known prompt as an unseen generalization test.

## 3. User Test 002 — Tkinter bulk file renamer with folder selection and preview

**User prompt (original wording):**

> hmm, okay make me an app using tkinter only which renames files in a folder, u should be able to select root folder, and a preview of files u want to name

**Model response — code as supplied:**

```python
import tkinter as tk
from tkinter import filedialog, messagebox
import os

def select_folder():
    folder_path = filedialog.askdirectory()
    if folder_path:
        list_files(folder_path)

def list_files(folder_path):
    files = os.listdir(folder_path)
    for file in files:
        if os.path.isfile(os.path.join(folder_path, file)):
            file_path = os.path.join(folder_path, file)
            print(f"File: {file_path}")
            rename_file(file_path)

def rename_file(file_path):
    new_name = input(f"Enter new name for {file_path}: ")
    if new_name:
        new_file_path = os.path.join(os.path.dirname(file_path), new_name)
        os.rename(file_path, new_file_path)
        print(f"Renamed {file_path} to {new_file_path}")

# Create the main window
root = tk.Tk()
root.title("File Renamer")

# Create a button to select the folder
select_button = tk.Button(root, text="Select Folder", command=select_folder)
select_button.pack(pady=20)

# Start the GUI event loop
root.mainloop()
```

**Model response — explanation as supplied (format normalized only):**

1. **Select Folder Function:** The `select_folder` function uses `filedialog.askdirectory()` to prompt the user to select a folder. If a folder is selected, it calls `list_files`.
2. **List Files Function:** Lists all files in the selected folder and prints paths. Then prompts the user to enter a new name for each file using `input()`.
3. **Rename File Function:** Prompts the user to enter a new name for a file and renames it using `os.rename()`.

**Model's example usage:** Save as `.py`, execute; select a folder; app lists files and prompts for names.

**Model's note:** Permissions are needed; it also mentioned installing `pyautogui` for mouse interaction, which is irrelevant to this Tkinter-only request and should not be suggested as a required dependency.

### Requirement-by-requirement evaluation (static)

| Requirement / expectation | Assessment | Evidence |
|---|---|---|
| Use Tkinter for UI | Partial | Creates Tk window/button, but most interaction is console-based |
| Browse/select root folder | Implemented in code | `filedialog.askdirectory()` |
| Preview files inside application | **Fail** | `print()` to terminal; no Listbox/Treeview/GUI preview |
| Select/edit proposed filenames in GUI | **Fail** | `input()` through console; no GUI entry widgets |
| Preview changes before rename | **Fail / likely intent** | Immediate rename per file, no before/after view |
| Safe confirmation before bulk changes | Missing | No confirmation dialog |
| Collision/invalid-name protection | Missing | Direct `os.rename()`; may fail or replace destinations depending on platform |
| Filesystem error handling | Missing | No `try/except` around list/rename operations |
| Respect Tkinter-only constraint | Partial | Uses standard library for filesystem, but console interaction undermines GUI requirement; `pyautogui` suggestion irrelevant |

### Root-cause hypotheses (not proven)

- **Underspecified GUI acceptance criteria:** The prompt was natural and short; the model may have treated console listing as a valid preview.
- **Weak requirement tracking:** It did not verify that preview and rename interactions happened inside Tkinter.
- **No execution/feedback loop:** The response was not subjected to GUI-interaction or safety tests before presentation.
- **Possible model capability or context limitations:** We cannot infer a general weakness from one sample; test prompt sensitivity before tuning.

### Required mitigating changes

1. Build **requirement extraction** that outputs checkable criteria; if the user asks for a GUI, all normal interaction must happen inside the GUI.
2. Add a **pre-response compliance gate**: explain how each requirement maps to widgets/functions and flag unmet or unverified requirements.
3. Implement a **Tkinter benchmark fixture** with synthetic directories, including `ttk.Treeview` or `Listbox` preview and editable proposed names. GUI tests require an actual graphical display or virtual display; do not claim they ran in an environment without one.
4. Add filesystem-safe batch-rename acceptance tests: validation before mutation; duplicate target checks; collision checks; extension handling where specified; cancel/confirmation; permission and partial-failure reporting; never overwrite files implicitly.
5. For untrusted code execution, use an OS-appropriate isolation strategy with filesystem scoping, no internet, time/memory caps, and no ambient home-drive access. Disable execution if safe isolation is unavailable.
6. Re-run the **original short prompt** and a **structured prompt** as a paired experiment using equal model parameters. Record full outputs, not just scores, and test whether better prompting solves the problem before fine-tuning.

## 4. Structured re-test prompt for Test 002

```text
Build a complete Python desktop application using ONLY tkinter, tkinter.ttk, and Python standard-library modules.

APPLICATION: Bulk File Renamer

REQUIREMENTS:
1. Provide a Browse button to select a folder.
2. Display the selected folder's files inside the GUI using ttk.Treeview.
3. Display two columns: Original Filename and New Filename.
4. Allow users to edit the proposed new filename for individual files.
5. Include a Preview button that updates the table without renaming anything.
6. Include an Apply Renames button that performs the operations only after confirmation.
7. Do not use input() or print() for user interaction.
8. Do not overwrite existing files. Validate duplicates and invalid filenames.
9. Preserve file extensions unless the user explicitly edits them.
10. Handle filesystem exceptions with messagebox dialogs.

Return complete executable code. Explain how each requirement is satisfied and disclose unverified behavior.
```

## 5. Chat session export — detailed implementation specification

### User experience

- Add **Export session** to chat header/session menu. Options: `Markdown (.md)`, `JSON (.json)`, and optionally `Bundle (.zip)` with both. Export only the selected session; label file with safe timestamp and short session ID; do not include secrets or filesystem paths by default when redaction is enabled.
- Export must include **full user messages and full assistant responses** in chronological order, preserving code block fences, newlines, and reasoning/explanations that were actually visible to the user. Do not attempt to export hidden reasoning or internal deliberation.
- Metadata: project name, export timestamp, session ID, selected model name and digest if known, quantization/context/temperature/top_p/seed if known, role/profile, backend, and per-message timing/token counts if supplied by runtime. `unknown` for unavailable fields.
- Feedback: rating/optional note, feedback timestamp, link to assistant message, and optional failure category. Ensure a feedback edit updates the record instead of generating detached duplicates.
- Include a toggle: **Include feedback/metadata**. Add **Redact potential secrets** option (default on; conservative pattern screening plus manual preview where feasible). Avoid exporting arbitrary local files unless explicitly attached and opted in.
- Add Copy entire session as Markdown; downloaded exports should also be importable by the Model Laboratory.

### Suggested JSON schema (illustrative)

```json
{
  "schema_version": "1.0",
  "session_id": "uuid",
  "exported_at": "ISO-8601 timestamp",
  "model": {"name": "unknown", "quantization": "unknown", "context_tokens": null},
  "messages": [
    {"id": "uuid", "role": "user", "content": "...", "timestamp": "ISO-8601 timestamp"},
    {"id": "uuid", "role": "assistant", "content": "...", "timestamp": "ISO-8601 timestamp",
     "feedback": {"rating": "down", "comment": "No GUI file preview"}}
  ]
}
```

### Storage and safety

- Use SQLite as the canonical session store, with stable UUID message IDs and foreign-key-linked feedback records. Schema migrations must preserve existing sessions.
- Use pure export functions for Markdown/JSON and unit tests for round-trip/import, Unicode, multiline prompts, fenced code blocks, empty sessions, multiple feedback edits, attachment references and 10k+ character responses.
- Do not require an online service; export operates fully offline. Limit access to local user sessions by default. Explicitly document that chat exports may contain private paths, code and data and should be reviewed before sharing.
- Allow directory selection for saved exports, and do not silently sync/export user conversations.

## 6. Evaluation and improvement workflow

1. **Reproduce:** capture same model/version/config for each prompt and save the raw response via session export.
2. **Extract requirements:** human-reviewed checklist; classify explicit versus inferred acceptance criteria.
3. **Static analysis:** parse Python; detect prohibited patterns in applicable contexts (e.g., `input()` for GUI interactions), inspect provided functions/widgets, run Ruff if present.
4. **Dynamic verification:** sandbox run suitable test cases. UI apps need GUI-specific checks; for filesystem changes, use temporary disposable data.
5. **Feedback loop:** show evidence-backed pass/fail/unknown per requirement; preserve user's rating; create training **candidates**, not automatic training data.
6. **Retest:** compare short natural prompt versus structured prompt, baseline versus agent + requirements gate, then later baseline versus fine-tuned model.
7. **Regression:** retain Test 001 as an easy code-generation case and Test 002 as a GUI requirement-following failure; diversify tests so improvements aren't optimized to just two prompts.

### Metrics to implement

- Syntax validity; runnable code percent; task-specific test pass rate; requirement satisfaction (verified/total, with unknown separate); file-operation safety; response time; tokens/sec if available; peak RAM/VRAM if available; user rating; regression rate; average repair attempts; and model comparison under equal settings.
- Report **provisional manual scores** separately from objective test results. Prior conversational qualitative scores were ~8.5/10 for sorting and ~3.5/10 for GUI; they are informal, subjective, and unexecuted, so **do not treat them as benchmark measurements**.

## 7. Prioritized Codex task backlog and acceptance gates

| Priority | Task | Acceptance |
|---|---|---|
| P0 | Session export Markdown + JSON | Complete chronological prompts/responses, code fences intact, import round-trip tests passing |
| P0 | Per-response feedback linkage | Existing request for feedback preserved; rating+comment persisted against exact response; editable |
| P0 | Store reproducibility metadata | No fabricated model IDs or timings; unavailable fields `unknown` |
| P1 | Requirements extraction/checklist | For Test 002, detects missing in-GUI preview, edits and confirmation; distinguish unknown |
| P1 | Safe test-run pathway | Run only in configured isolation; otherwise disabled and clearly explained |
| P1 | Benchmark fixtures for both tests | Sorting test matrix and disposable-folder Tkinter evaluation plan; actual run evidence attached |
| P1 | Structured prompt experiment | Full exported comparisons and results stored; consistent generation settings |
| P2 | Iterative repair / compliance feedback | Bounded repair attempts; regression checks; explain unresolved requirements |
| P2 | Dataset curation UI | User-reviewed candidates separated from held-out tests; no automatic training |
| P3 | Specialist adapter experiments | Only after robust baseline and enough validated data |

## 8. Deliverable format for Codex

- Implement actual source code, tests, migrations, and short developer documentation.
- Show changed files, verification commands and observed results; list any toolchain or GUI/headless blockers.
- Update `docs/experiment_log.md` with date, hypothesis, model config, tests actually run, results and next action.
- Do not modify prior project history to imply features were already complete.
- **Do not train any model as part of this report unless separately authorized.**

## 9. Codex starting instruction

> Read `PYFORGE_AI_CODEX_REVISED_MASTER_PLAN.md` and `FIRST_TEST_RUN_BY_USER.md`. Treat the two user-observed outputs as baseline evaluation evidence, not automated test results. Implement session export (Markdown and JSON), preserve linked per-response feedback, and build evidence-based requirement compliance checks before adding fine-tuning. Use synthetic temporary files for renamer tests and never modify user files during evaluation. Run tests, show exactly what passed, document what remains unverified, and keep the application offline-first.
