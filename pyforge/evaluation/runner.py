"""Run fixed prompts, recording raw outputs and observed resources."""

import ctypes
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import shutil
import subprocess

from pyforge.models.client import ModelClient


def load_tasks(path: Path) -> list[dict]:
    tasks = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(tasks, list) or len(tasks) < 20:
        raise ValueError("benchmark file must contain at least 20 tasks")
    ids = set()
    for task in tasks:
        if not isinstance(task, dict) or not all(isinstance(task.get(key), str) and task[key].strip() for key in ("id", "domain", "prompt", "review_focus")):
            raise ValueError("each task needs nonempty id, domain, prompt, and review_focus")
        if task["id"] in ids:
            raise ValueError(f"duplicate task id: {task['id']}")
        ids.add(task["id"])
    return tasks


def sample_resources() -> dict:
    sample = {"ram_available_mib": None, "gpu_free_mib": None}
    if os.name == "nt":
        class MemoryStatus(ctypes.Structure):
            _fields_ = [("length", ctypes.c_ulong), ("load", ctypes.c_ulong), ("total_physical", ctypes.c_ulonglong), ("available_physical", ctypes.c_ulonglong), ("total_page", ctypes.c_ulonglong), ("available_page", ctypes.c_ulonglong), ("total_virtual", ctypes.c_ulonglong), ("available_virtual", ctypes.c_ulonglong), ("available_extended_virtual", ctypes.c_ulonglong)]
        status = MemoryStatus()
        status.length = ctypes.sizeof(status)
        if ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(status)):
            sample["ram_available_mib"] = round(status.available_physical / (1024 ** 2), 1)
    executable = shutil.which("nvidia-smi")
    if executable:
        try:
            result = subprocess.run([executable, "--query-gpu=memory.free", "--format=csv,noheader,nounits"], capture_output=True, text=True, timeout=5, check=True)
            values = [int(line.strip()) for line in result.stdout.splitlines() if line.strip()]
            if values:
                sample["gpu_free_mib"] = values
        except (OSError, ValueError, subprocess.SubprocessError):
            pass
    return sample


def run_benchmark(client: ModelClient, tasks: list[dict], output: Path) -> tuple[int, int]:
    if output.exists():
        raise FileExistsError(f"Refusing to overwrite existing benchmark: {output}")
    output.parent.mkdir(parents=True, exist_ok=True)
    failures = 0
    with output.open("x", encoding="utf-8") as stream:
        for task in tasks:
            before = sample_resources()
            timestamp = datetime.now(timezone.utc).isoformat()
            try:
                reply = client.generate(task["prompt"])
                record = {"task_id": task["id"], "domain": task["domain"], "prompt": task["prompt"], "review_focus": task["review_focus"], "timestamp": timestamp, "model": reply.model, "raw_output": reply.text, "prompt_tokens": reply.prompt_tokens, "output_tokens": reply.output_tokens, "latency_seconds": reply.latency_seconds, "resources_before": before, "resources_after": sample_resources(), "test_result": "not_run_no_isolated_executor", "status": "generated"}
            except Exception as exc:
                failures += 1
                record = {"task_id": task["id"], "domain": task["domain"], "timestamp": timestamp, "status": "failed", "error_type": type(exc).__name__, "error": str(exc), "resources_before": before, "resources_after": sample_resources(), "test_result": "not_run_no_isolated_executor"}
            stream.write(json.dumps(record, ensure_ascii=False) + "\n")
            stream.flush()
    return len(tasks), failures
