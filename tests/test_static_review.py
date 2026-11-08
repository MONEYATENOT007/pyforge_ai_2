import json
from pathlib import Path
import tempfile
import unittest

from pyforge.evaluation.static_review import review_file, review_output


class StaticReviewTests(unittest.TestCase):
    def test_fenced_code_parses_but_missing_public_names_are_reported(self):
        review = review_output("refactor_duplicate", "Explanation.\n```python\ndef normalize_name(x):\n    return x.strip()\n```\n")
        self.assertTrue(review["ast_parse_ok"])
        self.assertEqual(review["missing_names"], ["lower_name", "upper_name"])

    def test_generated_code_is_never_executed(self):
        with tempfile.TemporaryDirectory() as temp:
            target = Path(temp) / "should_not_exist"
            code = f"```python\nfrom pathlib import Path\nPath({str(target)!r}).write_text('unsafe')\ndef sum_even(values): return 0\n```"
            review = review_output("core_sum_even", code)
            self.assertTrue(review["ast_parse_ok"])
            self.assertFalse(target.exists())

    def test_syntax_error_and_oversized_output_are_bounded(self):
        self.assertFalse(review_output("core_sum_even", "```python\ndef broken(:\n``` ")["ast_parse_ok"])
        self.assertEqual(review_output("core_sum_even", "x" * 100_001)["reason"], "code exceeds static review limit")

    def test_review_file_rejects_duplicate_ids_before_writing(self):
        with tempfile.TemporaryDirectory() as temp:
            source = Path(temp) / "results.jsonl"
            target = Path(temp) / "review.jsonl"
            source.write_text('\n'.join([json.dumps({"task_id": "core_sum_even", "raw_output": "def sum_even(x): return 0"})] * 2), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "duplicate"):
                review_file(source, target, {"core_sum_even"})
            self.assertFalse(target.exists())

    def test_review_file_writes_only_static_findings_and_refuses_overwrite(self):
        with tempfile.TemporaryDirectory() as temp:
            source = Path(temp) / "results.jsonl"
            target = Path(temp) / "review.jsonl"
            source.write_text(json.dumps({"task_id": "core_sum_even", "raw_output": "def sum_even(x): return 0"}), encoding="utf-8")
            self.assertEqual(review_file(source, target, {"core_sum_even"}), (1, 1, 0))
            row = json.loads(target.read_text(encoding="utf-8"))
            self.assertNotIn("raw_output", row)
            self.assertTrue(row["ast_parse_ok"])
            with self.assertRaises(FileExistsError):
                review_file(source, target, {"core_sum_even"})
