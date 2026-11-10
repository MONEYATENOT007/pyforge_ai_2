import unittest

from pyforge.evaluation.executable_cases import prepare_sort_case


class ExecutableCaseTests(unittest.TestCase):
    def test_extracts_single_python_block_and_builds_reviewed_sort_checks(self):
        response = "Here is code:\n```python\ndef bubble_sort(values):\n    return sorted(values)\n```"
        case = prepare_sort_case(response)
        self.assertIsNotNone(case)
        self.assertEqual(case.code, "def bubble_sort(values):\n    return sorted(values)")
        self.assertIn("bubble_sort", case.tests)
        self.assertIn("duplicate", case.contract)

    def test_rejects_multiple_blocks_and_unrecognized_interface(self):
        self.assertIsNone(prepare_sort_case("```python\ndef sort(x): return x\n```\n```python\nprint(1)\n```"))
        self.assertIsNone(prepare_sort_case("```python\ndef rename(path): return path\n```"))
        self.assertIsNone(prepare_sort_case("```python\ndef sort(a, b): return a\n```"))

    def test_accepts_plain_single_function(self):
        self.assertIsNotNone(prepare_sort_case("def sort_numbers(values):\n    return values"))


if __name__ == "__main__":
    unittest.main()
