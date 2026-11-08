# Phase 0 preflight (2026-11-08)

This report records observations from the current Windows session. `Get-CimInstance` drive inventory was denied access, so free space was read with .NET `System.IO.DriveInfo`. The new Python doctor initially could not run because `python.exe` is the WindowsApps placeholder. Python 3.14.10 was subsequently found at `C:\Users\hrdkk\AppData\Local\Programs\Python\Python314\python.exe`; pip 26.2.2 and the doctor both work through that full path. `py -0p` does not register it.

| Drive | Free GiB observed | DriveInfo class | Conservative planning status |
|---|---:|---|---|
| C: | 88.92 | Fixed, NTFS | Possible fast root only if confirmed SSD; 20–35 GiB soft budget keeps at least 50 GiB free |
| D: | 64.13 | Fixed, NTFS | No 25 GiB allocation while keeping 40 GiB free; use only after a smaller budget is agreed |
| E: | 31.19 | Fixed, NTFS | No allocation under the 40 GiB free-space floor |
| F: | 218.35 | Fixed, NTFS | Candidate for fast or bulk after media type and approval; initial budget depends on role |
| G: | 213.98 | Fixed, NTFS | Candidate for fast or bulk after media type and approval; initial budget depends on role |
| H: | 0.08 | Fixed, NTFS | No allocation |
| I: | 112.73 | Fixed, NTFS | Candidate for secondary or bulk after media type and approval; soft budget must leave 40 GiB free |

The doctor reported **12 logical CPUs, 15.95 GiB RAM, NVIDIA GeForce RTX 2060, 6144 MiB total VRAM, 5065 MiB free at observation time**. It reported the CPU identifier rather than a precise retail model. Ollama and Docker were not found on `PATH`. No model or package was downloaded. No directory was created outside the project.

## Proposed role assignment, pending confirmation

- Fast active root: C: is confirmed by the owner as SSD, with a strict limit of **40 GiB additional PyForge usage**. The brief's 50 GiB free-space floor is tighter at current free space, so the practical maximum is about 38.9 GiB; a 20–35 GiB soft budget is safer.
- Main project files: the owner approved F: (current project location). G: is an overflow option if F: runs low. Storage configuration paths will be set later at the owner's request.
- Bulk root: choose an approved HDD or secondary drive with adequate free space, preferably F: or G: if either is bulk storage. Start with a 50–120 GiB soft budget while retaining at least 40 GiB free.
- Workspace root: choose an approved development location. Do not assume it shares a drive with either model root.

These are **proposals, not allocations**. Physical media type, actual drive ownership, and permission to use each drive require user confirmation. Before a model download, install/locate Python 3.10+, run `python -m pyforge doctor`, choose roots, check the exact model artifact and license, and rerun free-space checks. `config/storage.example.json` intentionally leaves all roots null.

## Verification

- `git diff --check`: completed without whitespace errors in tracked changes.
- JSON example: parsed with PowerShell `ConvertFrom-Json`.
- `C:\Users\hrdkk\AppData\Local\Programs\Python\Python314\python.exe -m unittest discover -s tests -v`: **10 passed** after the benchmark tests were added.
- Same interpreter with `-m pyforge doctor --json`: **passed**, with the observations above.
- `-m pyforge benchmark --fake --output results/fake-baseline.jsonl`: **20 task records, 0 generation failures**; no generated code was executed or graded.
- Inference latency and RAM use: **not measured**. No model is installed or running through this package.
