from contextlib import redirect_stderr, redirect_stdout
from io import StringIO
import json
from pathlib import Path
import tempfile
import tomllib
import unittest

from pyforge import __version__
from pyforge.cli import main


class CliTests(unittest.TestCase):
    def test_local_version_uses_package_source(self):
        config = tomllib.loads((Path(__file__).resolve().parents[1] / "pyproject.toml").read_text(encoding="utf-8"))
        self.assertEqual(config["tool"]["setuptools"]["dynamic"]["version"]["attr"], "pyforge._version.VERSION")
        stdout = StringIO()
        with redirect_stdout(stdout), self.assertRaises(SystemExit) as exit_status:
            main(["--version"])
        self.assertEqual(exit_status.exception.code, 0)
        self.assertIn(__version__, stdout.getvalue())

    def test_doctor_json_runs_without_model(self):
        stdout = StringIO()
        with redirect_stdout(stdout):
            code = main(["doctor", "--json", "--storage-config", "config/storage.example.json"])
        report = json.loads(stdout.getvalue())
        self.assertEqual(code, 0)
        self.assertIn("drives", report)
        self.assertEqual(report["storage"]["bulk_root"]["status"], "unconfigured")

    def test_fake_benchmark_and_static_review_cli_roundtrip(self):
        with tempfile.TemporaryDirectory() as temp:
            results = Path(temp) / "results.jsonl"
            review = Path(temp) / "review.jsonl"
            stdout = StringIO()
            with redirect_stdout(stdout):
                self.assertEqual(main(["benchmark", "--fake", "--output", str(results)]), 0)
                self.assertEqual(main(["review", "--results", str(results), "--output", str(review)]), 0)
            self.assertEqual(len(results.read_text(encoding="utf-8").splitlines()), 20)
            self.assertEqual(len(review.read_text(encoding="utf-8").splitlines()), 20)
            self.assertIn("No code was executed", stdout.getvalue())
            original = results.read_bytes()
            with redirect_stderr(StringIO()):
                self.assertEqual(main(["benchmark", "--fake", "--output", str(results)]), 2)
            self.assertEqual(results.read_bytes(), original)

    def test_chat_rejects_non_loopback_before_request(self):
        stderr = StringIO()
        with redirect_stderr(stderr):
            code = main(["chat", "--url", "http://example.com:11434", "hello"])
        self.assertEqual(code, 2)
        self.assertIn("loopback", stderr.getvalue())
