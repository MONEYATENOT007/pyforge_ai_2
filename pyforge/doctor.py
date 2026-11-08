"""Read-only hardware and storage preflight."""

import ctypes
import json
import os
from pathlib import Path
import platform
import shutil
import subprocess
import sys
from urllib.error import URLError
from urllib.request import ProxyHandler, Request, build_opener

from .config import StorageConfig

GIB = 1024 ** 3


def _ollama_executable() -> str | None:
    configured = os.environ.get("PYFORGE_OLLAMA_EXE")
    if configured:
        executable = Path(configured).expanduser()
        return str(executable.absolute()) if executable.is_file() else None
    installed = shutil.which("ollama")
    if installed:
        return installed
    name = "ollama.exe" if os.name == "nt" else "ollama"
    portable = Path(__file__).resolve().parent.parent / "local_runtime" / "ollama" / name
    return str(portable) if portable.is_file() else None


def _windows_drives() -> list[Path]:
    mask = ctypes.windll.kernel32.GetLogicalDrives()
    return [Path(f"{chr(65 + i)}:\\") for i in range(26) if mask & (1 << i)]


def _drive_kind(path: Path) -> str:
    if os.name != "nt":
        return "unknown"
    names = {2: "removable", 3: "fixed", 4: "network", 5: "optical"}
    return names.get(ctypes.windll.kernel32.GetDriveTypeW(str(path)), "unknown")


def _memory_gib() -> float | None:
    if os.name == "nt":
        class MemoryStatus(ctypes.Structure):
            _fields_ = [("length", ctypes.c_ulong), ("load", ctypes.c_ulong), ("total_physical", ctypes.c_ulonglong), ("available_physical", ctypes.c_ulonglong), ("total_page", ctypes.c_ulonglong), ("available_page", ctypes.c_ulonglong), ("total_virtual", ctypes.c_ulonglong), ("available_virtual", ctypes.c_ulonglong), ("available_extended_virtual", ctypes.c_ulonglong)]
        status = MemoryStatus()
        status.length = ctypes.sizeof(status)
        if ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(status)):
            return round(status.total_physical / GIB, 2)
    elif hasattr(os, "sysconf"):
        try:
            return round(os.sysconf("SC_PHYS_PAGES") * os.sysconf("SC_PAGE_SIZE") / GIB, 2)
        except (ValueError, OSError):
            pass
    return None


def _gpu() -> dict:
    executable = shutil.which("nvidia-smi")
    if not executable:
        return {"status": "nvidia-smi unavailable"}
    try:
        result = subprocess.run([executable, "--query-gpu=name,memory.total,memory.free,driver_version", "--format=csv,noheader,nounits"], capture_output=True, text=True, timeout=5, check=True)
        return {"status": "ok", "gpus": [line.strip() for line in result.stdout.splitlines() if line.strip()], "memory_unit": "MiB; final field is driver version"}
    except (OSError, subprocess.SubprocessError) as exc:
        return {"status": "nvidia-smi failed", "detail": type(exc).__name__}


def _loaded_models() -> list[dict] | None:
    try:
        opener = build_opener(ProxyHandler({}))
        with opener.open(Request("http://127.0.0.1:11434/api/ps"), timeout=2) as response:
            data = json.load(response)
        if not isinstance(data, dict) or not isinstance(data.get("models"), list):
            return None
        return [{"name": item.get("name"), "size_vram_bytes": item.get("size_vram"), "context_length": item.get("context_length")} for item in data["models"] if isinstance(item, dict)]
    except (OSError, URLError, ValueError):
        return None


def _path_status(path: Path | None) -> dict:
    if path is None:
        return {"status": "unconfigured"}
    if not path.is_absolute():
        return {"path": str(path), "status": "not absolute"}
    anchor = Path(path.anchor)
    if not anchor.exists():
        return {"path": str(path), "status": "drive or mount missing"}
    if path.exists() and not path.is_dir():
        return {"path": str(path), "status": "exists but is not a directory"}
    ancestor = next((item for item in (path, *path.parents) if item.exists()), None)
    try:
        free = shutil.disk_usage(anchor).free / GIB
    except OSError:
        free = None
    return {"path": str(path), "status": "exists" if path.is_dir() else "would need creation", "parent_writable_estimate": os.access(ancestor, os.W_OK) if ancestor else False, "drive_free_gib": round(free, 2) if free is not None else None}


def collect_report(storage: StorageConfig) -> dict:
    roots = _windows_drives() if os.name == "nt" else [Path("/")]
    drives = []
    for root in roots:
        kind = _drive_kind(root)
        try:
            usage = shutil.disk_usage(root)
            drives.append({"root": str(root), "kind": kind, "media": "SSD/HDD unknown", "total_gib": round(usage.total / GIB, 2), "free_gib": round(usage.free / GIB, 2), "allocation_candidate": (kind == "fixed" or os.name != "nt") and usage.free / GIB >= 40})
        except OSError as exc:
            drives.append({"root": str(root), "kind": kind, "status": type(exc).__name__})
    return {
        "os": platform.platform(),
        "python": sys.version.split()[0],
        "cpu": platform.processor() or "unknown",
        "logical_cpus": os.cpu_count(),
        "ram_gib": _memory_gib(),
        "gpu": _gpu(),
        "runtimes": {"ollama": _ollama_executable(), "docker": shutil.which("docker"), "git": shutil.which("git")},
        "loaded_models": _loaded_models(),
        "drives": drives,
        "storage": {"fast_root": _path_status(storage.fast_root), "bulk_root": _path_status(storage.bulk_root), "workspace_root": _path_status(storage.workspace_root)},
        "allocation_guidance": {"fast_ssd_soft_budget_gib": "20-35 if 50 GiB remains free", "secondary_ssd_soft_budget_gib": "25-60 if 40 GiB remains free", "bulk_hdd_soft_budget_gib": "50-120 if 40 GiB remains free", "note": "Budgets are proposals only. Verify physical media and approve each drive before configuring roots or downloading."},
    }
