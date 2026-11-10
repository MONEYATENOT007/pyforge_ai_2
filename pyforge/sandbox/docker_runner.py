"""Run candidate Python only in the dedicated F: WSL Docker daemon.

This is a bounded diagnostic backend, not a security boundary for hostile code.
It never mounts Windows files or the Docker socket into a test container.
"""

from __future__ import annotations

import ast
import json
import os
import subprocess
import threading
import time
from dataclasses import dataclass
from uuid import uuid4

IMAGE = "python:3.14-slim@sha256:9aaa474097d094040649f2162a627c0049b408f52138d980916788d80f04802f"
DISTRO = "PyForgeSandbox"
MAX_SOURCE_BYTES = 64 * 1024
MAX_OUTPUT_BYTES = 64 * 1024
TIMEOUT_SECONDS = 8.0

_BOOTSTRAP = r'''
import contextlib
import io
import json
import sys
import traceback

class LimitedOutput(io.StringIO):
    def write(self, value):
        if self.tell() + len(value) > 32768:
            raise RuntimeError("output limit exceeded")
        return super().write(value)

payload = json.load(sys.stdin)
out = LimitedOutput()
err = LimitedOutput()
scope = {"__name__": "candidate"}
status = "passed"
detail = ""
try:
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        exec(compile(payload["code"], "candidate.py", "exec"), scope)
        exec(compile(payload["tests"], "checks.py", "exec"), scope)
except AssertionError:
    status = "wrong_answer"
    detail = traceback.format_exc(limit=5)
except BaseException:
    status = "runtime_error"
    detail = traceback.format_exc(limit=5)
print("PYFORGE_RESULT:" + json.dumps({"status": status, "detail": detail,
      "stdout": out.getvalue(), "stderr": err.getvalue()}))
'''


@dataclass(frozen=True)
class SandboxResult:
    status: str
    detail: str
    stdout: str = ""
    stderr: str = ""
    elapsed_seconds: float = 0.0


def _read_bounded(pipe, chunks: list[bytes], limit_hit: threading.Event) -> None:
    total = 0
    try:
        while block := pipe.read(4096):
            total += len(block)
            if total > MAX_OUTPUT_BYTES:
                limit_hit.set()
                break
            chunks.append(block)
    finally:
        pipe.close()


def _send_payload(pipe, payload: bytes) -> None:
    try:
        pipe.write(payload)
        pipe.flush()
    except (BrokenPipeError, OSError):
        pass
    finally:
        pipe.close()


def _remove_container(name: str) -> None:
    try:
        subprocess.run(
            ["wsl.exe", "-d", DISTRO, "-u", "root", "--exec", "docker", "rm", "-f", name],
            capture_output=True, timeout=5, check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        pass


def run_python_case(code: str, tests: str, *, enabled: bool = False) -> SandboxResult:
    """Run one reviewed test fixture. Callers must opt in for each execution.

    ``tests`` must come from trusted, reviewed fixtures, never model output.
    """
    if not enabled:
        return SandboxResult("sandbox_unavailable", "Isolated execution is disabled")
    if not isinstance(code, str) or not isinstance(tests, str) or not tests.strip():
        return SandboxResult("not_testable", "A Python snippet and reviewed tests are required")
    if len(code.encode("utf-8")) > MAX_SOURCE_BYTES or len(tests.encode("utf-8")) > MAX_SOURCE_BYTES:
        return SandboxResult("not_testable", "Source or tests exceed the 64 KiB limit")
    try:
        ast.parse(code)
    except SyntaxError as exc:
        return SandboxResult("syntax_error", f"{exc.msg} at line {exc.lineno}")
    try:
        ready = subprocess.run(
            ["wsl.exe", "-d", DISTRO, "-u", "root", "--exec", "docker", "image", "inspect", IMAGE],
            stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, timeout=40, check=False,
            creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return SandboxResult("sandbox_unavailable", f"Docker preflight failed: {exc}")
    if ready.returncode != 0:
        return SandboxResult("sandbox_unavailable", ready.stderr.decode("utf-8", errors="replace")[:2048])
    name = "pyforge-test-" + uuid4().hex
    command = [
        "wsl.exe", "-d", DISTRO, "-u", "root", "--exec", "docker", "run",
        "--rm", "--name", name, "--pull", "never", "--interactive",
        "--network", "none", "--read-only", "--cap-drop", "ALL",
        "--security-opt", "no-new-privileges", "--user", "65534:65534",
        "--pids-limit", "32", "--memory", "256m", "--memory-swap", "256m",
        "--cpus", "1", "--ipc", "none", "--log-driver", "none",
        "--tmpfs", "/tmp:rw,nosuid,nodev,noexec,size=32m", "--workdir", "/tmp",
        IMAGE, "python", "-I", "-B", "-c", _BOOTSTRAP,
    ]
    started = time.monotonic()
    try:
        proc = subprocess.Popen(command, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                stderr=subprocess.PIPE, creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0)
    except OSError as exc:
        return SandboxResult("sandbox_unavailable", str(exc))
    payload = json.dumps({"code": code, "tests": tests}).encode("utf-8")
    stdout: list[bytes] = []
    stderr: list[bytes] = []
    limit_hit = threading.Event()
    workers = [
        threading.Thread(target=_send_payload, args=(proc.stdin, payload), daemon=True),
        threading.Thread(target=_read_bounded, args=(proc.stdout, stdout, limit_hit), daemon=True),
        threading.Thread(target=_read_bounded, args=(proc.stderr, stderr, limit_hit), daemon=True),
    ]
    for worker in workers:
        worker.start()
    expired = False
    try:
        while proc.poll() is None:
            if limit_hit.is_set() or time.monotonic() - started >= TIMEOUT_SECONDS:
                expired = True
                proc.kill()
                break
            time.sleep(0.025)
        proc.wait(timeout=2)
    except subprocess.TimeoutExpired:
        expired = True
        proc.kill()
    finally:
        for worker in workers:
            worker.join(timeout=1)
        if expired:
            _remove_container(name)
    elapsed = round(time.monotonic() - started, 3)
    if limit_hit.is_set():
        return SandboxResult("runtime_error", "Container output exceeded 64 KiB", elapsed_seconds=elapsed)
    if expired:
        return SandboxResult("timeout", "Container exceeded the 8 second wall-clock limit", elapsed_seconds=elapsed)
    raw_out = b"".join(stdout).decode("utf-8", errors="replace")
    raw_err = b"".join(stderr).decode("utf-8", errors="replace")
    marker = "PYFORGE_RESULT:"
    line = next((line for line in reversed(raw_out.splitlines()) if line.startswith(marker)), None)
    if proc.returncode != 0 or line is None:
        return SandboxResult("sandbox_unavailable", (raw_err or raw_out or "Container failed")[:2048], elapsed_seconds=elapsed)
    try:
        result = json.loads(line[len(marker):])
        if result["status"] not in {"passed", "wrong_answer", "runtime_error"}:
            raise ValueError("unknown result status")
    except (ValueError, KeyError, TypeError):
        return SandboxResult("sandbox_unavailable", "Container returned an invalid result", elapsed_seconds=elapsed)
    return SandboxResult(result["status"], result["detail"][:2048], result["stdout"][:32768],
                         result["stderr"][:32768], elapsed)
