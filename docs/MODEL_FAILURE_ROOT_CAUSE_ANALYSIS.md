# PyForge AI model failure root-cause analysis

**Date:** 2026-11-08

**Package:** 0.3.1

**Evaluated models:** `qwen2.5-coder:1.5b-instruct-q4_K_M` (digest `d7372fd828518a4d38b1eb196c673c31a85f2ed302b3d1e406c4c2d1b64a0668`) and `qwen2.5-coder:7b-instruct-q4_K_M` (digest `dae161e27b0e90dd1856c8bb3209201fd6736d8eb66298e75ed87571486f4364`), Ollama 0.40.14

**Evidence:** Original user export at `C:\Users\hrdkk\Downloads\pyforge-chat-20261108-e9a09316.md` (read only), [redacted Session 02 fixture](../tests/fixtures/session02_cases.json), [diagnostic script](../scripts/diagnose_model_failures.py), and ignored full-response JSON files listed below. All five fixture response IDs, prompts and responses were verified as present in the original export. Probes use the redacted fixture so the raw export stays outside the repository.

## 1. Executive summary

The installed 1.5B model generated a plausible bubble sort, but fresh probes reproduced the GUI and repair failures. The Tkinter-only correction still produced PyQt; the NameError repair repeated an import already present while leaving the unbound `matplotlib` reference. Structured renamer and dashboard prompts produced more relevant descriptions but still contained undefined names and missing behavior. This is strong evidence of a **small-model capability limit on these multi-component tasks**, alongside specific integration gaps: the app does not execute code safely, its static checker recognizes only narrow prompt forms, and reported tracebacks are stored but not automatically added to repair prompts.

The representative 1.5B prompts used 111–1,374 Ollama input tokens, below the configured 4,096-token context; the original export's largest recorded input was 1,903 tokens. The recent source and Tkinter correction were sent in the repair probe, so context overflow does not explain that reproduced failure. Longer conversations can still lose earlier turns because the app applies an 8,192-character history budget before Ollama tokenization. No generated program was executed, so there is **no runtime pass rate**.

After owner approval, a 7B Q4_K_M model was installed on F: and compared on the same seven prompts. It improved some static properties but still failed the core GUI and NameError repair requirements, while generating about 5.6 times more slowly. **Decision:** retain 1.5B as the default and keep 7B available as an optional manual comparison model. An isolated correctness benchmark is needed before a default switch. Do not fine-tune yet.

## 2. Method and reproduced failures

The original export was inspected read only. The probe calls the same `stream_exchange` path as chat, with the General profile, its generated checklist, `num_ctx=4096`, and `temperature=0`. The four representative cases are an algorithm prompt, the fixture's renamer prompt, the Tkinter-only dashboard correction with its preceding source, and the NameError correction with recent history. Three additional prompt variants test explicit requirements and minimal-patch instructions. Full prompts, responses, metadata, and static findings are in `results/model-failure-diagnostic-20261108.json`; this ignored local file is retained on F: and is not committed because it contains raw model output. Focused repair variants are in `results/model-failure-repair-structured-v2-20261108.json` and `results/model-failure-repair-guided-20261108.json`.

| Probe | Input / output tokens | Ollama total time | Syntax / Ruff F821 | Requirement evidence |
|---|---:|---:|---|---|
| Bubble sort | 111 / 381 | 2.26 s | Parsed; no F821 | No built-in sort call; sorting behavior **unexecuted**. |
| Tkinter renamer | 193 / 819 | 4.82 s | Parsed; `root_folder` undefined | Folder chooser and Listbox population are present, but no editable new name, preview-before-apply, or confirmation. It attempts to move selected files to a second folder using the same name. |
| Tkinter-only dashboard correction | 1,188 / 1,117 | 6.99 s | Parsed; `QTimer` undefined | PyQt persists, GPU uses `psutil.cpu_percent`, CPU sampling blocks the GUI, and no historical series is retained. |
| NameError repair | 1,374 / 785 | 5.05 s | Parsed; `matplotlib` and `QTimer` undefined | Repeats `import matplotlib.pyplot as plt`, already present in the source; leaves the bare `matplotlib.backends...` reference and the other dashboard defects. |
| Structured renamer | 261 / 1,111 | 6.64 s | Parsed; 16 F821 occurrences including `tree`, `entry`, `folder_path`, `ttk` | Treeview insertion is attempted, but referenced widgets and folder state are local to `main()` and unavailable to callbacks. Rename proceeds without a confirmation dialog; prose claims otherwise. |
| Structured dashboard | 135 / 981 | 5.83 s | Parsed; `gpu_label` undefined | Uses Tkinter, but GPU is a hardcoded `50`, graphs use random values, and `cpu_percent(interval=1)` blocks. The old checker returned **no checklist** for this wording; matcher fixed in 0.3.1. |
| Structured minimal repair, 1,024 output-token cap | 954 / 674 | 4.16 s | Patch was not applied or compiled | `done_reason=stop`; proposed diff adds the already-present `matplotlib.pyplot` import. NameError remains. This response was not cut off by the 1,024-token cap. |

The guided repair variant explicitly stated that `import matplotlib.pyplot as plt` was already present. It still repeated that line, produced no valid corrective diff, and looped through duplicated prose; the 768-token experimental cap ended the response. The response was generated before completion-reason capture was added, so its exact Ollama stop reason was **not recorded**. A separate 128-token algorithm cap test returned `done_reason=length` and a partial code block. PyForge 0.3.1 now records that state as `output_limited` rather than complete.

The original export's first dashboard answer **did import `QTimer`**; its later Tkinter-only revision and repair omitted it. The fresh dashboard correction in this report also omits it. This distinction matters when attributing the undefined-name failure to a specific turn. Static import availability was checked with `importlib.util.find_spec` in the F: venv for top-level imports seen in the six fresh code blocks: `PyQt5`, `matplotlib`, `numpy`, `os`, `psutil`, `sys`, `time`, and `tkinter` were all discoverable. That check did not import or execute candidate code and does not prove its imports or GUI behavior work at runtime.

**Meaning of “parsed”:** `ast.parse` and `compile(..., mode="exec")` accepted extracted Python text; neither command executed it. Ruff F821 is a static undefined-name check. Neither verifies imports at runtime, GUI wiring, file safety, or algorithm correctness. The patch responses were not applied to source or tested. No code from model responses was run or imported on the host. Disposable chat databases were used only to save probe conversations.

## 3. Implementation audit

| Question | Observed implementation and evidence | Assessment |
|---|---|---|
| Loaded model at initial audit | Local `/api/tags` then listed only the 1.5B Q4_K_M model; after probes `/api/ps` showed it loaded, `size_vram=1,169,382,440` bytes, context 4096. The UI lets the user select from installed models. | 7B was subsequently installed and measured in Section 8. |
| Complete history | `pyforge/chat/service.py` fetches stored messages. `build_chat_messages` in `pyforge/chat/profiles.py` packs recent turns under `min(12000, context*2)` characters and stops at the first older turn that will not fit. | Recent history, **not the complete conversation**, is sent. A large latest response can exclude older corrections. |
| Corrections and previous code | Messages are stored in SQLite and selected recent user/assistant turns go to Ollama. For the repair probe, two of four supplied history messages were sent: the latest dashboard source and Tkinter-only correction; the older dashboard prompt/response were dropped. | Relevant source and correction were present in this probe. No automatic retrieval of older source. |
| Context truncation | The app's 8,192-character prefilter is a heuristic, not a token counter. Probe input counts were all below 4096, with 1374 the maximum here. The original export recorded a maximum of 1903 input tokens across seven assistant turns. | No evidence that Ollama context overflow caused these observed failures; longer chats remain at risk. |
| Qwen format | `OllamaClient.chat_stream` sends a `system`/`user`/`assistant` message array to `/api/chat`. Local `/api/show` exposes the model's `<|im_start|>...<|im_end|>` chat template. PyForge does not hand-build template tokens. | Format is compatible through Ollama; no observed formatting bug. |
| System prompt | General profile asks for accuracy, concision and honest test claims; `stream_exchange` appends a narrow requirement checklist for recognized prompts. It gives no explicit diagnose-to-diff-to-verification procedure. | Useful honesty instruction; weak repair workflow. The checklist did not make this model reliable. |
| Generation settings | `/api/chat` sends `num_ctx=4096`, `temperature=0`. It does not set `top_p`, `seed`, or a default `num_predict`; these are recorded as unknown unless explicitly supplied. A diagnostic-only optional `num_predict` parameter was added. | Temperature is reasonable for repeatable coding probes. Other defaults and completion limits should be measured, not guessed. Zero temperature does not make all runs identical. |
| Debugging inputs | A user can paste source/traceback in chat; recent prior assistant code is usually in history. The **Report a problem** fields persist expected/actual/traceback linked to a response, but `stream_exchange` reads message content only. The exported fixture includes the short `NameError` text, not a full traceback. | Actual full traceback and saved problem report are **not automatically injected** into repair context. |
| Tools | `review_requirements` and `static_review` parse AST without executing; evaluation queue stores analysis cases. Chat's Run Tests button is disabled. Ruff was installed in the project F: venv for this diagnostic, not wired into normal chat. | Static evidence exists; isolated execution, GUI and disposable-file tests do not. |
| Output/context limits | The ordinary app does not set `num_predict`, and its prior stream record ignored Ollama `done_reason`. The controlled 128-token probe demonstrably stopped mid-code with `done_reason=length`; 0.3.1 records and labels this condition. | The original failure responses are not proven truncated. Explicit caps can truncate code, and now receive an incomplete label. |

The UI still provides selected-session Markdown/JSON exports, response-linked feedback, and problem reports. This work did not change their storage schema or remove any of those actions.

## 4. Root causes, corrections, and verification path

| Category | Evidence and likely impact | Confidence | Correction and verification |
|---|---|---|---|
| A. Foundation-model capability | The 1.5B model repeats PyQt after a Tkinter-only correction and repeats an existing import after being told it is already there. The paired 7B probes improve some surface constraints but retain core GUI/repair failures. | High for these probes; sample is small. | Extend the completed text/static pairing to broader held-out GUI/repair tasks and a safe test harness before attributing a stable model advantage. |
| B. Prompting | General profile lacks a repair protocol. Even a requirement checklist and minimal-diff instruction did not fix the sampled repair. | Medium. | For repairs, package the exact source, traceback and explicit acceptance checks; require an actual diff and report unverified behavior. Test multiple cases, not one. |
| C. History/context | The 8,192-character budget omitted older turns, but kept latest source and correction in this repair. Inputs were below 4096 tokens. | High that it is **not the proximate cause here**; medium future risk. | Replace the character heuristic with measured token budgeting and a visible omitted-history summary; verify with long synthetic chats and API input counts. |
| D. Inference configuration | Temperature 0 is appropriate; default `top_p`/seed and output limit are unspecified. A 128-token cap cut off valid code; ordinary app has no explicit cap. | Medium. | Record effective options and Ollama `done_reason`; compare bounded output settings while checking completeness. The latter is implemented in 0.3.1. |
| E. Missing execution/debugging tools | AST parsing passed programs with F821 errors and nonfunctional GUI paths; Run Tests remains disabled. | High. | Build a restricted, disposable runner with no network, resource limits, synthetic renamer files, and GUI smoke tests. Only then run generated code and targeted regressions. |
| F. Requirement verification | The prior checker missed “performance dashboard” and can mark Treeview insertion as static evidence while the widget is unbound. It does not detect a hardcoded GPU `50` or random graphs. | High. | The dashboard wording matcher is fixed in 0.3.1 with a regression test. Add data-flow and fake-telemetry checks, then validate against human-reviewed examples and isolated tests; do not promote static evidence to runtime pass. |

## 5. Corrective changes and actual verification

- Added an optional output-token limit to the Ollama chat adapter, primarily for bounded probes. Existing chat calls keep the previous no-explicit-cap behavior. Ollama `done_reason=length` is saved as `output_limited` and shown in the chat metric line.
- Expanded dashboard requirement recognition to cover “performance dashboard” and CPU/GPU/RAM monitoring with graphs; checker version is `session02-static-v2`.
- Added a repeatable diagnostic script that writes full prompts/responses and provenance under ignored `results/`, parses syntax, and calls Ruff F821. It never runs generated code. Ruff 0.17.4 was installed only into `F:\pyforge_ai_2\.venv`.
- `python -m unittest discover -s tests` passed **56 tests**, including output-limit, dashboard-checklist and UI-label regressions. Ruff F821 on repository source/tests passed; `pip check` found no broken requirements. This is a repository test result, not a generated-app pass. Fresh Streamlit AppTest against the current F: database had zero exceptions and displayed v0.3.1; port 8501 health returned HTTP 200. CLI, source version and both editable metadata records matched 0.3.1 after regenerating a stale ignored root `egg-info` record. The diagnostic script's existing-output guard was exercised and refused an overwrite.

## 6. 1.5B versus 7B decision and hardware

| Item | Observed at diagnostic time | Implication |
|---|---|---|
| Installed models at initial audit | `/api/tags` listed only 1.5B Q4_K_M; existing 1.5B was retained. | Owner later approved the 7B pull; paired results are in Section 8. |
| GPU | RTX 2060, 6144 MiB total; one `nvidia-smi` snapshot showed 2926 MiB used and 3020 MiB free. Ollama reported the loaded 1.5B model fully in VRAM at ~1.17 GB. | 7B Q4 plus context may offload or need memory freed; measure residency rather than assume full GPU fit. |
| RAM | 17.13 GB total, 3.43 GB available in one `psutil` snapshot. | Tight headroom for CPU offload at that moment; close other workloads before a controlled 7B run. |
| Disk | F: had ~228.9 GB free; G: ~229.8 GB; C: ~90.3 GB. Portable launcher sets `OLLAMA_MODELS=F:\pyforge_ai_2\local_runtime\models`; the 1.5B manifest was found there. | F: has capacity for a 7B download without using C: for model storage; still verify Ollama's effective path before download. |

The table above is the **pre-download snapshot**. Current install, model residency and paired measurements are in Section 8. No generated-code runtime comparison was possible because the isolated backend is still absent.

## 7. Known limitations and next tasks

1. The original export was found in the owner's Downloads folder and matched the five redacted fixture examples. It was read only and never treated as executable instructions. The fresh probes are new samples from the installed model, not replays of the original full conversation.
2. No isolated backend is configured; targeted algorithm, GUI and file-operation runtime tests, import execution, and real traceback reproduction remain **not run**. Synthetic test directories cannot make host execution of generated code safe by themselves.
3. Ruff F821 and the existing checker can miss dynamic failures and can overstate static coverage. A patch-shaped answer cannot be declared fixed merely because a small Python fence parses.
4. A single temperature-0 sample per prompt family is diagnostic, not a statistically stable pass rate or unseen benchmark.
5. Next: implement a safe execution backend and disposable GUI/file fixtures; then a verified minimal-repair loop that uses saved problem reports and keeps original source, diff, tests, and rollback history. Keep chat export and feedback intact.
6. The approved 7B Q4 model is now installed on F: and completed the paired text/static comparison in Section 8. A default-model decision still needs isolated correctness tests on broader tasks. No fine-tuning or agent orchestration is warranted yet.

## 8. Approved 7B Q4 paired comparison

The owner approved the download. The [official Ollama tag](https://ollama.com/library/qwen2.5-coder:7b-instruct-q4_K_M) lists a 7.62B Q4_K_M model of about 4.7 GB. Ollama verified its SHA-256 digest and wrote the manifest under `F:\pyforge_ai_2\local_runtime\models`; `/api/tags` reports both the new 7B tag and the retained 1.5B tag with Q4_K_M quantization. The first pull stalled at 39%; a resumed pull completed without deleting the partial file.

The same diagnostic script ran **seven cases per model** with the General profile, identical prompt and history text, identical generated system checklists, `num_ctx=4096`, `temperature=0`, and `num_predict=2048`. These equalities were checked programmatically for every case. Both `/api/show` responses have Qwen chat-template markers and no model-specific parameter override; `top_p` and seed were not explicitly set. Full returned text, token counts, completion reasons and snapshots are saved locally in ignored `results/paired-1p5b-20261108.json` and `results/paired-7b-20261108.json`. One run per case is diagnostic, not a stable pass-rate estimate.

| Case | 1.5B result | 7B result |
|---|---|---|
| Simple sorting | Bubble sort, parsed, no built-in sort call. | Bubble sort, parsed, no built-in sort call. Neither was executed. |
| Tkinter renamer | Produced `input()`/`print()` interactions and used an unset folder attribute; the response reached the 2,048-token limit while looping through prose. | Produced a populated Treeview and confirmation dialog, but put `tk.StringVar` objects into table values with no working edit action. It checks target existence during mutation, so batch safety and duplicate validation are not established. Prose falsely claims names can be edited in the Treeview. |
| Tkinter-only dashboard correction | Continued with PyQt, `QTimer` undefined and CPU data used as GPU. | Used Tkinter and had no Ruff F821 warning, but still used `psutil.cpu_percent()` as GPU, updated Tk widgets from a worker thread, and redrew only current values without history. |
| NameError repair | Returned installation advice and no source patch; mistook `NameError` for a missing package. | Returned a full PyQt program still referencing unbound `matplotlib` and `QTimer`, plus `float("0%")`; it did not fix the reported error. |
| Structured renamer | Ruff found 18 undefined-name occurrences; preview path can rename files. | No Ruff F821 warning, but no filename editor or confirmation exists, and Apply asks for a second folder. Prose says all requirements are verified despite code evidence to the contrary. |
| Structured dashboard | Used `root.after` for some labels but blocked CPU sampling, never updated the graph, and used an unverified GPU API. | Reports GPU unavailable and attempts histories, but updates Tk widgets from a worker thread, stores string GPU values in numeric graph calculations (a definite type error), and leaves histories unbounded. Prose claims `root.after` and a 100-point bound that are absent from code. |
| Structured minimal repair | Repeated an import already in source; output reached the 2,048-token limit while repeating irrelevant caveats. | Returned a short diff that also adds the existing import, leaving the bare `matplotlib` reference unresolved. Neither patch was applied or executed. |

**Measured speed and residency:** Median generation throughput across the seven cases was **170.7 output tokens/s** for 1.5B and **30.7 output tokens/s** for 7B; 7B was about **5.6× slower** in this small local sample. Cold-load durations were 20.2 s and 52.1 s respectively (one sample each; excluded from throughput). Ollama `/api/ps` reported 1.5B loaded size and VRAM size both **1.169 GB**; for 7B it reported **5.152 GB** loaded and **4.199 GB** in VRAM, indicating partial CPU offload. System-wide GPU memory reached **2,715 MiB** in the 1.5B run and **5,547 MiB** in the 7B run; minimum available system RAM snapshots were **3.89 GB** and **3.16 GB**. These are system snapshots, not model-exclusive peaks or layer counts.

The downloaded model used about 4.7 GB of F: space. C: free space changed little during the pull, then fell by roughly 5.5 GB during the later inference interval; the cause was not established. Both model manifests and Ollama temporary paths remain on F:, and the observed C: change is below the owner's 40 GB project cap. Monitor C: again before longer runs.

The 7B tag appears alongside 1.5B in a fresh Streamlit AppTest render with zero exceptions; 1.5B remains the selected default. Port 8501 health returned HTTP 200. After the diagnostic-script change, the full repository suite passed 56 tests, Ruff F821 on repository source/tests passed, `pip check` passed, and CLI/source/installed metadata remained at v0.3.1. The browser session itself was not inspected. No generated program was executed, so syntax and static findings must not be called runtime correctness. The paired sample supports **keeping 1.5B as default for speed** while offering 7B for manual comparison; it does not show that either model can reliably deliver the requested GUI apps or repair. The next meaningful gate is a restricted runner with disposable GUI/file fixtures and a broader held-out task set.
