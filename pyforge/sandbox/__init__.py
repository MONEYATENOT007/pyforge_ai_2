"""Opt-in, container-backed execution of small trusted test cases."""

from .docker_runner import SandboxResult, run_python_case

__all__ = ["SandboxResult", "run_python_case"]
