"""Synthetic, disposable checks for the opt-in WSL container backend."""

import os
import unittest

from pyforge.evaluation.executable_cases import prepare_sort_case
from pyforge.sandbox import run_python_case


class SandboxPreflightTests(unittest.TestCase):
    def test_disabled_by_default(self):
        self.assertEqual(run_python_case("print('unused')", "assert True").status,
                         "sandbox_unavailable")

    def test_syntax_rejected_without_execution(self):
        result = run_python_case("def broken(:", "assert True", enabled=True)
        self.assertEqual(result.status, "syntax_error")

    def test_missing_reviewed_tests_rejected(self):
        self.assertEqual(run_python_case("x = 1", "", enabled=True).status,
                         "not_testable")


@unittest.skipUnless(os.environ.get("PYFORGE_SANDBOX_TEST") == "1",
                     "Set PYFORGE_SANDBOX_TEST=1 for real disposable container tests")
class SandboxIntegrationTests(unittest.TestCase):
    def test_chat_sort_fixture_runs_in_container(self):
        response = """```python
def bubble_sort(values):
    data = list(values)
    for end in range(len(data), 0, -1):
        for i in range(end - 1):
            if data[i] > data[i + 1]:
                data[i], data[i + 1] = data[i + 1], data[i]
    return data
```"""
        case = prepare_sort_case(response)
        self.assertIsNotNone(case)
        result = run_python_case(case.code, case.tests, enabled=True)
        self.assertEqual(result.status, "passed", result)

    def test_correct_and_incorrect_answers(self):
        good = run_python_case("def add(a, b): return a + b",
                               "assert add(2, 3) == 5", enabled=True)
        self.assertEqual(good.status, "passed", good)
        bad = run_python_case("def add(a, b): return a - b",
                              "assert add(2, 3) == 5", enabled=True)
        self.assertEqual(bad.status, "wrong_answer", bad)

    def test_runtime_error_is_reported(self):
        result = run_python_case("raise ValueError('synthetic failure')",
                                 "assert True", enabled=True)
        self.assertEqual(result.status, "runtime_error", result)
        self.assertIn("ValueError", result.detail)

    def test_restricted_container_has_no_windows_mount_or_network(self):
        code = """import os
import socket
assert os.getuid() == 65534
assert not os.path.exists('/mnt/c/Windows')
try:
    open('/etc/pyforge_write_probe', 'w')
except OSError:
    pass
else:
    raise AssertionError('root filesystem is writable')
try:
    socket.create_connection(('1.1.1.1', 53), timeout=0.2)
except OSError:
    pass
else:
    raise AssertionError('container can reach the network')
"""
        result = run_python_case(code, "assert True", enabled=True)
        self.assertEqual(result.status, "passed", result)

    def test_timeout_removes_container(self):
        result = run_python_case("while True: pass", "assert True", enabled=True)
        self.assertEqual(result.status, "timeout", result)


if __name__ == "__main__":
    unittest.main()
