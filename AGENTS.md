# Repository work notes

- Read `progress.md`, `PYFORGE_AI_CODEX_REVISED_MASTER_PLAN.MD` and relevant user test reports before changing the project. The revised plan supersedes the original build brief in stage order.
- Update `progress.md` in the same change as every source, test, configuration or documentation edit. State completed work, actual verification, and remaining work. Keep historical measurements in `docs/experiment_log.md` and the phase reports.
- Change `pyforge/_version.py` for a new user-visible package milestone. That file is the sole package-version source; keep `progress.md` and release notes in sync. Run `python -m pyforge --version` and package metadata checks after a version change.
- Chat launchers enable Streamlit's source watcher and automatic rerun on save. Check port 8501 health and a Streamlit render after UI changes. Use `scripts/restart_chat.ps1` only when the server is unavailable, stale, or its launch configuration changes; it must verify port ownership before stopping any process.
- Do not execute generated code on the host. Keep Run Tests disabled until an isolated backend and disposable-file tests are verified.
- Keep main artifacts on F: and project use of C: below the owner's 40 GB cap; G: is overflow.
