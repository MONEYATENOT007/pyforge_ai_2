# Training data preparation

PyForge v0.3.3 can prepare **explicitly reviewed** examples for a future local fine-tuning experiment. This command does not train, execute generated code, inspect the chat database, or mark a response correct. The owner-reported 7B improvement is useful feedback; a held-out correctness comparison has not yet measured it.

## Current gate

The revised plan places isolated testing and a held-out benchmark before fine-tuning. On 2026-11-10, Docker was absent, WSL2 had no listed distribution, the F: venv had no PyTorch/Transformers/PEFT/Accelerate/bitsandbytes packages, and the chat database held zero marked training candidates. The existing 20 mixed-domain tasks are a prototype evaluation bank, not the planned 120–200 validated Core Python tasks. No training run is ready or claimed.

## Candidate file

Create a UTF-8 JSON list yourself from material you have the right to use. Do not feed exported chats directly into training. Each object needs:

| Field | Meaning |
|---|---|
| `id`, `family_id` | Stable example ID and a group ID shared by variants of the same task. A family stays in one split. |
| `task_type` | `code` or `explanation`. Code requires an actual isolated test result before approval. |
| `prompt`, `response` | The reviewed input and ideal answer. They are written verbatim to train or validation JSONL. |
| `source`, `license` | Human-recorded provenance and usage rights. `unknown`, `unverified`, and `none` are rejected. This tool cannot independently establish legal rights. |
| `reviewed_by`, `reviewed_at`, `review_status` | Human review record; status must be `approved`, and time must be an ISO 8601 timestamp with timezone. The command does not authenticate the reviewer. |
| `verification_status` | `isolated_test_passed` for code; `human_reviewed` or `isolated_test_passed` for explanations. |
| `verification_reference` | Required when claiming an isolated test passed; point to the saved report. The command checks that the reference is present, not that the report is genuine. |
| `split` | One of `train`, `validation`, `held_out`; each split needs at least one example. Assign deliberately before training. |

The command rejects duplicate IDs, normalized duplicate prompts, related `family_id` values across splits, and train/validation prompts that match the supplied evaluation task bank. Normalization catches case and whitespace differences, not paraphrases. A human must review related tasks and private content before approval.

Run from the repository root, with both input and output on F: or G::

```powershell
.\.venv\Scripts\python.exe -m pyforge curate-data --input F:\path\to\reviewed-candidates.json --output F:\pyforge_ai_2\results\curated-run-001
```

The output directory must be new. It receives `train.jsonl`, `validation.jsonl`, and `manifest.json`. The JSONL files contain user/assistant message pairs and provenance. The manifest records counts, source/evaluation-file hashes, output hashes, and hashes of held-out prompts. Held-out prompt and response text remain in the original input file and are **not** copied to the output. Keep that input private and out of Git. Future training code must read only `train.jsonl`, use validation only for tuning, and reserve held-out tasks for final comparison.

Before any real training run, implement and verify an isolated executor, expand and review the task bank, collect genuinely approved examples, verify the local training backend and memory use, and record a baseline on untouched weights. The 7B Ollama Q4 file is an inference artifact; it is not itself a ready-to-train adapter base.
