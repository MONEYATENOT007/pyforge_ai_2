import unittest
from unittest.mock import patch
import os
from pathlib import Path
import tempfile

from pyforge.config import StorageConfig
from pyforge.doctor import collect_report


class DoctorTests(unittest.TestCase):
    def test_report_contains_unconfigured_storage_and_no_write(self):
        with patch("pyforge.doctor._gpu", return_value={"status": "unavailable"}), patch("pyforge.doctor._loaded_models", return_value=None), patch("pyforge.doctor._ollama_executable", return_value=None), patch("pyforge.doctor.shutil.which", return_value=None):
            report = collect_report(StorageConfig())
        self.assertIn("os", report)
        self.assertIn("drives", report)
        self.assertEqual(report["storage"]["fast_root"]["status"], "unconfigured")
        self.assertIsNone(report["runtimes"]["ollama"])
        self.assertIn("note", report["allocation_guidance"])

    def test_explicit_portable_runtime_path_is_detected_read_only(self):
        from pyforge.doctor import _ollama_executable

        with tempfile.TemporaryDirectory() as temp:
            executable = Path(temp) / "ollama.exe"
            executable.write_bytes(b"fake")
            with patch.dict(os.environ, {"PYFORGE_OLLAMA_EXE": str(executable)}):
                self.assertEqual(_ollama_executable(), str(executable))
            self.assertEqual(executable.read_bytes(), b"fake")
