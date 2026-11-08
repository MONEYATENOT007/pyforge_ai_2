"""Repeat Session 02 failures with local Ollama; never execute generated code.

Responses and metrics are written to an ignored F: results path. Syntax parsing and
Ruff read candidate text only. This is an analysis probe, not a sandboxed test run.
"""

import argparse
import ast
from datetime import datetime, timezone
import json
from pathlib import Path
import subprocess
import sys
import threading
import time
from urllib.request import urlopen

import psutil

from pyforge.chat.service import stream_exchange
from pyforge.chat.store import ChatStore
from pyforge.evaluation.requirements import review_requirements
from pyforge.evaluation.static_review import extract_python_code
from pyforge.models.ollama_client import OllamaClient


DEFAULT_MODEL = "qwen2.5-coder:1.5b-instruct-q4_K_M"
CONTEXT = 4096
ROOT = Path(__file__).resolve().parents[1]
CASE_IDS = ("algorithm", "renamer", "dashboard", "repair", "renamer_structured",
            "dashboard_structured", "repair_structured", "repair_guided")


def cases(fixture: dict) -> list[dict]:
    source = {case["case_id"]: case for case in fixture["cases"]}
    dashboard_first = source["dashboard_initial"]
    dashboard_second = source["dashboard_revision"]
    return [
        {"id": "algorithm", "prompt": "Write Python code to sort a list of integers ascending without sort() or sorted().", "history": []},
        {"id": "renamer", "prompt": source["renamer_initial"]["prompt"], "history": []},
        {"id": "dashboard", "prompt": dashboard_second["prompt"], "history": [
            ("user", dashboard_first["prompt"]), ("assistant", dashboard_first["response"])]},
        {"id": "repair", "prompt": source["dashboard_repair"]["prompt"], "history": [
            ("user", dashboard_first["prompt"]), ("assistant", dashboard_first["response"]),
            ("user", dashboard_second["prompt"]), ("assistant", dashboard_second["response"])]},
        {"id": "renamer_structured", "prompt": (
            "Build a complete Python desktop bulk file renamer using only tkinter, tkinter.ttk and the standard library.\n"
            "Requirements: Browse to select a folder. Show original and proposed filenames in a populated Treeview. "
            "Let the user edit proposed names. Preview must not rename files. Apply only after confirmation. "
            "Reject duplicate or colliding targets and invalid names without overwriting. Preserve extensions unless edited. "
            "Show filesystem errors in messagebox dialogs. Do not use print() or input() for interaction. "
            "Return complete code, then state which requirements are unverified."), "history": []},
        {"id": "dashboard_structured", "prompt": (
            "Build a Tkinter-only Python performance dashboard. Use no PyQt or Qt. Show live CPU and RAM utilization "
            "from psutil. Show NVIDIA GPU utilization from a real GPU source, or clearly display unavailable; never "
            "copy CPU values into GPU. Draw bounded historical time-series graphs in Tkinter Canvas. Use root.after "
            "for periodic updates and nonblocking CPU sampling. Keep all UI work on the main thread. Return complete "
            "code and identify any behavior you could not verify."), "history": []},
        {"id": "repair_structured", "prompt": (
            "The following source raised NameError: name 'matplotlib' is not defined. Fix that exact error with the "
            "smallest code patch. Show a unified diff, and state other defects that remain. Do not claim the app has "
            "been executed or fully repaired.\n\nSOURCE:\n" + extract_python_code(dashboard_second["response"]) +
            "\nTRACEBACK (only user-reported detail available):\nNameError: name 'matplotlib' is not defined"), "history": []},
        {"id": "repair_guided", "prompt": (
            "Review the existing imports and the exact failing reference before editing. The source already contains "
            "`import matplotlib.pyplot as plt`; do not add that same import again. Diagnose why the bare name "
            "`matplotlib` is unresolved. Return only the smallest unified diff that fixes this NameError, then list "
            "remaining defects without claiming execution.\n\nSOURCE:\n" + extract_python_code(dashboard_second["response"]) +
            "\nUSER-REPORTED ERROR:\nNameError: name 'matplotlib' is not defined"), "history": []},
    ]


def static_checks(response: str, prompt: str, context: list[str]) -> dict:
    if "```diff" in response:
        return {"syntax": "not_checked_patch_not_applied", "undefined_names": None,
                "requirements": "not_checked_patch_not_applied",
                "runtime_execution": "not_run_no_isolated_backend"}
    code = extract_python_code(response).strip()
    try:
        ast.parse(code)
        compile(code, "candidate.py", "exec")  # Builds a code object; does not run it.
        syntax = "passed"
    except (SyntaxError, ValueError, RecursionError) as exc:
        syntax = f"failed: {type(exc).__name__}: {exc}"
    ruff = subprocess.run(
        [sys.executable, "-m", "ruff", "check", "--select", "F821", "--output-format", "json", "--stdin-filename", "candidate.py", "-"],
        input=code, text=True, capture_output=True, check=False, timeout=30,
    )
    try:
        undefined = [{"code": issue["code"], "message": issue["message"], "location": issue["location"]}
                     for issue in json.loads(ruff.stdout)]
    except (json.JSONDecodeError, KeyError, TypeError):
        undefined = None
    return {"syntax": syntax, "ruff_exit": ruff.returncode, "undefined_names": undefined,
            "ruff_stderr": ruff.stderr, "requirements": review_requirements(prompt, response, context=context),
            "runtime_execution": "not_run_no_isolated_backend"}


def resource_snapshot() -> dict:
    memory = psutil.virtual_memory()
    snapshot = {"ram_available_bytes": memory.available, "gpu_used_mib": None, "gpu_utilization_percent": None}
    try:
        result = subprocess.run(
            ["nvidia-smi", "--query-gpu=memory.used,utilization.gpu", "--format=csv,noheader,nounits"],
            text=True, capture_output=True, check=True, timeout=5,
        )
        used, utilization = (part.strip() for part in result.stdout.splitlines()[0].split(",")[:2])
        snapshot.update(gpu_used_mib=int(used), gpu_utilization_percent=int(utilization))
    except (OSError, subprocess.SubprocessError, IndexError, ValueError):
        pass
    return snapshot


def sample_resources(stop: threading.Event, samples: list[dict]) -> None:
    while not stop.is_set():
        samples.append(resource_snapshot())
        stop.wait(1)


def loaded_model_snapshot(model: str) -> dict | None:
    try:
        with urlopen("http://127.0.0.1:11434/api/ps", timeout=5) as response:
            payload = json.load(response)
        return next((item for item in payload.get("models", []) if item.get("name") == model), None)
    except (OSError, ValueError, TypeError):
        return None


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True, help="new JSON result file under F: workspace")
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument("--only", choices=CASE_IDS)
    parser.add_argument("--case-ids", nargs="+", choices=CASE_IDS)
    parser.add_argument("--max-output-tokens", type=int)
    args = parser.parse_args()
    output = args.output.resolve()
    database = output.with_suffix(".sqlite3")
    if ROOT not in output.parents or output.exists() or database.exists():
        parser.error("output and companion database must be new paths inside this project")
    output.parent.mkdir(parents=True, exist_ok=True)
    fixture = json.loads((ROOT / "tests/fixtures/session02_cases.json").read_text(encoding="utf-8"))
    store = ChatStore(database)
    client = OllamaClient(args.model, context=CONTEXT, timeout=300, max_output_tokens=args.max_output_tokens)
    if args.model not in client.list_models():
        parser.error(f"model is not installed on the local Ollama server: {args.model}")
    record = {"probe": "model-failure-diagnostic-v1", "started_at": datetime.now(timezone.utc).isoformat(),
              "source": "redacted tests/fixtures/session02_cases.json; verified against original export",
              "model": args.model, "context": CONTEXT, "profile": "General", "metadata": client.model_metadata(),
              "max_output_tokens": args.max_output_tokens,
              "cases": []}
    with output.open("x", encoding="utf-8") as stream:
        json.dump(record, stream)
    for case in cases(fixture):
        if args.only and case["id"] != args.only:
            continue
        if args.case_ids and case["id"] not in args.case_ids:
            continue
        print(f"Starting {case['id']}...", flush=True)
        session = store.create_session(case["id"])
        for role, content in case["history"]:
            store.add_message(session, role, content)
        samples: list[dict] = []
        stop = threading.Event()
        sampler = threading.Thread(target=sample_resources, args=(stop, samples), daemon=True)
        sampler.start()
        wall_start = time.monotonic()
        try:
            for _ in stream_exchange(store, client, session, case["prompt"], "General", CONTEXT):
                pass
            message = store.messages(session)[-1]
            context = [content for role, content in case["history"] if role == "user"]
            result = {"id": case["id"], "prompt": case["prompt"], "history": case["history"],
                      "response": message["content"], "run": message["run"], "metrics": message["metrics"],
                      "static": static_checks(message["content"], case["prompt"], context)}
            print(f"{case['id']}: {message['metrics'].get('output_tokens')} output tokens; {result['static']['syntax']}", flush=True)
        except Exception as exc:
            result = {"id": case["id"], "prompt": case["prompt"], "history": case["history"],
                      "error": f"{type(exc).__name__}: {exc}"}
            print(f"{case['id']}: {result['error']}", flush=True)
        finally:
            stop.set()
            sampler.join(timeout=7)
        result["wall_seconds"] = time.monotonic() - wall_start
        result["resources"] = {
            "min_ram_available_bytes": min((sample["ram_available_bytes"] for sample in samples), default=None),
            "max_gpu_used_mib": max((sample["gpu_used_mib"] for sample in samples if sample["gpu_used_mib"] is not None), default=None),
            "samples": len(samples), "scope": "system-wide snapshots; not model-exclusive peak",
            "ollama_loaded_model_after": loaded_model_snapshot(args.model),
        }
        record["cases"].append(result)
        output.write_text(json.dumps(record, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Saved {len(record['cases'])} cases to {output}", flush=True)


if __name__ == "__main__":
    main()
