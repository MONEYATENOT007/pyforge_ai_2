# Phase 1 baseline report (2026-11-08)

## Local setup

With the owner's approval, portable Ollama 0.40.14 was downloaded from the [official release](https://github.com/ollama/ollama/releases/tag/v0.40.14) into `local_runtime/downloads` on F:. Its Windows ZIP SHA-256 matched the published value `65d68cade6cf6375f398b518224f8c8a15e062387f38cf477abfc848de7e7e29`. It was extracted into `local_runtime/ollama`; no global Ollama install was made. The server was started by `scripts/start_local_ollama.ps1`, which sets `OLLAMA_MODELS` to `local_runtime/models`, `OLLAMA_HOST` to `127.0.0.1:11434`, and `OLLAMA_NO_CLOUD=1` in its process environment. Server logs confirm all three settings. The model was pulled only after confirming the F: model path.

Ollama lists [`qwen2.5-coder:1.5b-instruct-q4_K_M`](https://ollama.com/library/qwen2.5-coder%3A1.5b-instruct), digest `d7372fd82851`, as installed. Its F: model files total **986,069,032 bytes**. The Ollama model page lists Q4_K_M and Apache 2.0; [Qwen's upstream license](https://huggingface.co/Qwen/Qwen2.5-Coder-1.5B-Instruct/blob/cc932d8a05bf5a3dcd700f50584714d17fc4d03a/LICENSE) is Apache 2.0.

## Measurements

| Observation | Result | Limit |
|---|---:|---|
| First `chat` request, cold | 84.013 s, 41 prompt tokens, 17 output tokens | Includes model load and initial GPU compilation; one request only |
| Second `chat` request, warm | 0.044 s, 36 prompt tokens, 2 output tokens | Tiny response with prompt cache benefit |
| 20-task baseline | 20 generated, 0 generation failures; mean latency 0.791 s, range 0.177–2.233 s | Warm model; no correctness tests executed |
| RAM available during baseline snapshots | about 5,282–5,440 MiB | Before/after snapshots, not peak memory use |
| GPU free during baseline snapshots | about 3,683–3,771 MiB | Before/after snapshots, not peak VRAM use |
| Ollama model residency | 1.2 GB, 100% GPU, 4096 context, per `ollama ps` | One loaded model at observation time |
| F: runtime files | 4,837,835,701 bytes | Includes 1,601,954,968-byte downloaded ZIP, 2,249,786,895-byte extracted runtime, 986,069,032-byte model, and small logs |
| Free disk after setup | F: about 213.84 GiB; C: about 87.32 GiB | C: fell from about 88.9 GiB during work; only 468 bytes were found in Ollama's C: user directory, so the remaining change is not attributed to PyForge without evidence |

The 20-task fixed prompt set is in `pyforge/evaluation/tasks.json`; raw results and resource snapshots are in `results/qwen-1.5b-baseline.jsonl` on F:. The fake baseline is in `results/fake-baseline.jsonl`. Both result files are ignored by Git. The benchmark runner labels every result `not_run_no_isolated_executor`; generation success does not imply functional correctness.

## Manual answer review

Several clear failures appeared without executing any output:

- `core_sum_even` silently skips invalid values and booleans instead of raising `TypeError`.
- `core_chunk` uses `len()` and slicing, so it fails for general iterables and generators.
- `core_counter` exposes a writable `value` property and accepts booleans as integers.
- `core_lru` does not reject non-positive capacity.
- `edge_parse_int` rejects positive strings with leading zeros, which the task permits.
- `edge_median` returns an `int` for odd counts although the task asks for a float.
- `edge_safe_divide` accepts booleans through Python's `bool` subclass of `int`.
- `refactor_duplicate` removes the requested public function signatures.
- `backend_fastapi_validation` does not enforce `quantity >= 1` and changes `/items` to `/items/`.
- `automation_atomic_text` creates its temporary file in the default temp directory rather than the target directory, so replacement may not be atomic across volumes.

These findings show that the local model is useful for generating candidate code but is not reliable enough to apply patches without tool checks and review. Other answers remain unverified; this report does not assign a pass rate.

## Additional Phase 1 verification

The test suite was expanded from 10 to **22 passing tests**. It now covers a real loopback HTTP exchange against a test server, missing-model and malformed-response handling, non-loopback URL rejection, benchmark failure records, CLI roundtrips, read-only doctor behavior, and static review that never executes a generated code sample. The suite was run with `-W error::ResourceWarning` after fixing an unclosed HTTP 404 response; it passed without warnings. `pip check` also found no broken requirements.

The baseline was repeated twice with the same 20 prompts and temperature zero:

| Run | Generation failures | Mean warm request latency | Output comparison with first run |
|---|---:|---:|---|
| Initial | 0/20 | 0.791 s | Reference |
| Repeat 1 | 0/20 | 0.877 s | All 20 raw outputs identical |
| Repeat 2 | 0/20 | 0.800 s | 2/20 raw outputs changed (`refactor_branch`, `automation_atomic_text`) |

The second repeat's `automation_atomic_text` answer placed the temporary file in the target directory, unlike the initial answer, but it still did not clean up a temporary file if writing failed. Temperature zero therefore did not guarantee byte-identical output on this setup. Each run was inspected with `pyforge review`: **20/20** extracted code blocks parsed as Python in each run, and **1/20** lacked explicitly requested top-level names (`refactor_duplicate`). These are static observations, not functional test results.

A wheel build succeeded using pip with build dependencies downloaded to temporary storage on F:. The wheel included `pyforge/evaluation/tasks.json` and a `pyforge` console entry point. A wheel installed into an isolated F: target directory ran `review` from outside the source folder. That packaging check exposed and led to a doctor fix: `PYFORGE_OLLAMA_EXE` can now identify the portable runtime when PyForge is installed elsewhere. The fix passed a focused read-only test; the wheel has not been rebuilt since that last change.

At the end of this verification pass, F: still had about 213.84 GiB free and C: about 88.6 GiB free. The earlier C: reading of 87.32 GiB was transient; no lasting multi-gigabyte C: allocation was observed.

## Next phase

Build repository scanning and retrieval, then a secure isolated test runner before any automated correctness grade or patch application. Keep the 7B model deferred until the 1.5B baseline and tooling are evaluated. Storage config roots remain unset as requested; the portable launcher uses project-relative paths on F:. G: remains unused overflow. C: has the owner's 40 GiB additional-use cap.
