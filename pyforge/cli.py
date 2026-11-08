"""Command line entry point."""

import argparse
import json
import os
from pathlib import Path
import sys

from . import __version__

from .config import load_storage
from .doctor import collect_report
from .event_log import emit
from .evaluation.runner import load_tasks, run_benchmark
from .evaluation.static_review import review_file
from .models.fake_client import FakeClient
from .models.ollama_client import ModelUnavailable, OllamaClient


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="pyforge", description="Offline-first Python assistant")
    parser.add_argument("--version", action="version", version=f"PyForge AI {__version__}")
    sub = parser.add_subparsers(dest="command", required=True)
    doctor = sub.add_parser("doctor", help="read-only hardware and storage preflight")
    doctor.add_argument("--json", action="store_true", help="machine-readable output")
    doctor.add_argument("--storage-config", help="optional JSON config path")
    chat = sub.add_parser("chat", help="one prompt to local Ollama")
    chat.add_argument("prompt", nargs="?", help="prompt text; otherwise read stdin")
    chat.add_argument("--model", default=os.environ.get("PYFORGE_MODEL", "qwen2.5-coder:1.5b-instruct-q4_K_M"))
    chat.add_argument("--url", default=os.environ.get("PYFORGE_OLLAMA_URL", "http://127.0.0.1:11434"))
    chat.add_argument("--timeout", type=float, default=120)
    chat.add_argument("--context", type=int, default=4096)
    benchmark = sub.add_parser("benchmark", help="run fixed prompts without executing generated code")
    benchmark.add_argument("--tasks", type=Path, default=Path(__file__).resolve().parent / "evaluation/tasks.json")
    benchmark.add_argument("--output", type=Path, required=True, help="new JSONL file on an approved drive")
    benchmark.add_argument("--fake", action="store_true", help="use deterministic fake model for smoke test")
    benchmark.add_argument("--model", default=os.environ.get("PYFORGE_MODEL", "qwen2.5-coder:1.5b-instruct-q4_K_M"))
    benchmark.add_argument("--url", default=os.environ.get("PYFORGE_OLLAMA_URL", "http://127.0.0.1:11434"))
    benchmark.add_argument("--timeout", type=float, default=360, help="seconds allowed per local model response")
    review = sub.add_parser("review", help="parse generated code without executing it")
    review.add_argument("--results", type=Path, required=True, help="benchmark JSONL to review")
    review.add_argument("--output", type=Path, required=True, help="new review JSONL file")
    review.add_argument("--tasks", type=Path, default=Path(__file__).resolve().parent / "evaluation/tasks.json")
    args = parser.parse_args(argv)
    if args.command == "doctor":
        try:
            report = collect_report(load_storage(args.storage_config))
        except (OSError, ValueError, json.JSONDecodeError) as exc:
            parser.exit(2, f"Storage config error: {exc}\n")
        if args.json:
            print(json.dumps(report, indent=2))
        else:
            print(f"OS: {report['os']} | Python: {report['python']} | CPU: {report['cpu']} ({report['logical_cpus']} logical) | RAM: {report['ram_gib']} GiB")
            print(f"GPU: {report['gpu']} | Runtimes: {report['runtimes']}")
            print("Drives (physical SSD/HDD type requires separate verification):")
            for drive in report["drives"]:
                print(f"  {drive}")
            print("Chosen storage paths:")
            for role, status in report["storage"].items():
                print(f"  {role}: {status}")
            print(f"Proposed allocation: {report['allocation_guidance']}")
        return 0
    if args.command == "benchmark":
        try:
            tasks = load_tasks(args.tasks)
            client = FakeClient() if args.fake else OllamaClient(args.model, args.url, timeout=args.timeout)
            count, failures = run_benchmark(client, tasks, args.output)
        except (OSError, ValueError, json.JSONDecodeError) as exc:
            print(f"Benchmark error: {exc}", file=sys.stderr)
            return 2
        print(f"Recorded {count} tasks ({failures} generation failures) in {args.output}; generated code was not executed or tested.")
        return 1 if failures else 0
    if args.command == "review":
        try:
            tasks = load_tasks(args.tasks)
            count, parsed, missing = review_file(args.results, args.output, {task["id"] for task in tasks})
        except (OSError, ValueError, json.JSONDecodeError) as exc:
            print(f"Review error: {exc}", file=sys.stderr)
            return 2
        print(f"Reviewed {count} outputs: {parsed} parsed as Python; {missing} lack requested top-level names. No code was executed.")
        return 0
    prompt = args.prompt if args.prompt is not None else sys.stdin.read()
    if not prompt.strip():
        parser.error("chat requires a nonempty prompt")
    try:
        reply = OllamaClient(args.model, args.url, args.timeout, args.context).generate(prompt)
    except (ModelUnavailable, ValueError) as exc:
        print(f"Local model unavailable: {exc}", file=sys.stderr)
        return 2
    print(reply.text)
    emit("model_reply", model=reply.model, prompt_tokens=reply.prompt_tokens, output_tokens=reply.output_tokens, latency_seconds=round(reply.latency_seconds or 0.0, 3))
    return 0
