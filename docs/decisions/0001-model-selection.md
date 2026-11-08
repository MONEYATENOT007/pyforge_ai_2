# Decision 0001: one local coding model first

The first active model is Qwen2.5-Coder 1.5B Instruct Q4_K_M through portable Ollama on the owner's RTX 2060 6 GB. Ollama lists the artifact at 986 MB with an Apache 2.0 license; see the [Ollama artifact page](https://ollama.com/library/qwen2.5-coder%3A1.5b-instruct) and [upstream license](https://huggingface.co/Qwen/Qwen2.5-Coder-1.5B-Instruct/blob/cc932d8a05bf5a3dcd700f50584714d17fc4d03a/LICENSE).

The 1.5B model was chosen as a small first baseline, not because it is known to be best. Three 20-task runs generated outputs quickly after a slow first load, but manual review found clear specification misses. Quantization reduces weight memory and may reduce quality. The 4096-token context setting is smaller than a repository; retrieval will be needed later. One model plays six instruction profiles sequentially; no specialist weights have been trained.

The planned 7B Q4 comparison is deferred until a credible isolated grading harness exists and the download is separately approved. Its roughly 4.7 GB weight size would leave less of the 6 GB VRAM for KV cache and runtime buffers. A 7B inference run does not imply feasible 7B fine-tuning. A 3B model is also deferred pending a separate license and memory check.

The selection rule for a future default is measured correctness and constraint compliance on held-out tasks, then latency and RAM/VRAM use under equal prompts, context, runtime settings and hardware. No current run establishes a functional pass rate because generated code has not been executed in isolation.
