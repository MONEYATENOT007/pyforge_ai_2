import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from pyforge.evaluation.runner import load_tasks, run_benchmark
from pyforge.models.fake_client import FakeClient


TASKS = Path(__file__).resolve().parent.parent / "pyforge/evaluation/tasks.json"


class BenchmarkTests(unittest.TestCase):
    def test_fixture_has_twenty_unique_reviewable_tasks(self):
        tasks = load_tasks(TASKS)
        self.assertEqual(len(tasks), 20)
        self.assertTrue({"fastapi", "pyqt6", "tkinter", "traceback", "refactor"}.issubset({task["domain"] for task in tasks}))

    def test_fake_run_records_outputs_without_claiming_tests_passed(self):
        with tempfile.TemporaryDirectory() as temp, patch("pyforge.evaluation.runner.sample_resources", return_value={"ram_available_mib": None, "gpu_free_mib": None}):
            output = Path(temp) / "benchmark.jsonl"
            count, failures = run_benchmark(FakeClient("pass"), load_tasks(TASKS), output)
            rows = [json.loads(line) for line in output.read_text(encoding="utf-8").splitlines()]
            self.assertEqual((count, failures), (20, 0))
            self.assertEqual(len(rows), 20)
            self.assertTrue(all(row["raw_output"] == "pass" and row["test_result"] == "not_run_no_isolated_executor" for row in rows))
            self.assertTrue(all(row["run"]["model_digest"] == "unknown" for row in rows))
            self.assertEqual(len({row["run"]["task_set_sha256"] for row in rows}), 1)
            with self.assertRaises(FileExistsError):
                run_benchmark(FakeClient(), load_tasks(TASKS), output)

    def test_model_failure_is_recorded_without_claiming_success(self):
        class FailsOnce:
            calls = 0

            def generate(self, prompt):
                self.calls += 1
                if self.calls == 1:
                    raise RuntimeError("model failed")
                return FakeClient("ok").generate(prompt)

        with tempfile.TemporaryDirectory() as temp, patch("pyforge.evaluation.runner.sample_resources", return_value={"ram_available_mib": None, "gpu_free_mib": None}):
            output = Path(temp) / "benchmark.jsonl"
            count, failures = run_benchmark(FailsOnce(), load_tasks(TASKS), output)
            rows = [json.loads(line) for line in output.read_text(encoding="utf-8").splitlines()]
            self.assertEqual((count, failures), (20, 1))
            self.assertEqual(rows[0]["status"], "failed")
            self.assertEqual(rows[0]["test_result"], "not_run_no_isolated_executor")
            self.assertEqual(rows[1]["status"], "generated")
