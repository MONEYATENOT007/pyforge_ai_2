"""Static regressions from the redacted Session 02 chat fixture."""

import json
from pathlib import Path
import unittest

from pyforge.evaluation.requirements import review_requirements
from pyforge.evaluation.static_review import extract_python_code

FIXTURE = Path(__file__).resolve().parent / "fixtures" / "session02_cases.json"


class Session02Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        data = json.loads(FIXTURE.read_text(encoding="utf-8"))
        assert data["redacted"] is True
        cls.cases = {item["case_id"]: item for item in data["cases"]}

    def review(self, name):
        case = self.cases[name]
        result = review_requirements(case["prompt"], case["response"], context=case["context"])
        self.assertEqual(result["syntax"], "static_evidence")
        return {item["id"]: item for item in result["requirements"]}

    def test_renamer_revision_does_not_pass_for_unused_widgets(self):
        initial = self.review("renamer_initial")
        revised = self.review("renamer_revision")
        self.assertEqual(initial["folder_select"]["status"], "static_evidence")
        for key in ("gui_file_preview", "gui_name_edit", "preview_before_apply", "confirmation"):
            self.assertEqual(initial[key]["status"], "failed", key)
            self.assertEqual(revised[key]["status"], "failed", key)
        self.assertTrue(revised["gui_file_preview"]["claim_conflict"])
        self.assertEqual(revised["collision_guard"]["status"], "unknown")

    def test_dashboard_correction_and_repair_preserve_failed_requirements(self):
        first = self.review("dashboard_initial")
        revised = self.review("dashboard_revision")
        repair = self.review("dashboard_repair")
        self.assertEqual(first["tkinter_only"]["status"], "unknown")  # PyQt was initially allowed.
        self.assertEqual(first["unresolved_references"]["status"], "unknown")  # QTimer was imported.
        for result in (revised, repair):
            for key in ("tkinter_only", "gpu_metric", "live_graphs",
                        "nonblocking_updates", "unresolved_references",
                        "invalid_literal_conversion"):
                self.assertEqual(result[key]["status"], "failed", key)
            self.assertIn("matplotlib", result["unresolved_references"]["evidence"])
            self.assertIn("QTimer", result["unresolved_references"]["evidence"])

    def test_python_fence_after_shell_install_block_is_selected(self):
        response = "Install:\n```sh\npip install psutil\n```\n```python\nx = 1\n```"
        self.assertEqual(extract_python_code(response).strip(), "x = 1")

    def test_unrelated_new_prompt_does_not_inherit_old_dashboard_requirements(self):
        result = review_requirements(
            "Write a function to count vowels", "def count_vowels(text):\n    return sum(c in 'aeiou' for c in text)",
            context=["Create a task manager with CPU GPU RAM and live graphs using Tkinter"],
        )
        self.assertEqual(result["requirements"], [])


if __name__ == "__main__":
    unittest.main()
