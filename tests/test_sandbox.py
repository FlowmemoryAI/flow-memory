import unittest

from flow_memory.action import PythonSandbox


class SandboxTests(unittest.TestCase):
    def test_allows_safe_arithmetic(self) -> None:
        result = PythonSandbox().execute("x = sum(range(5))\nprint(x)")
        self.assertTrue(result.success)
        self.assertIn("10", result.stdout)
        self.assertEqual(result.globals["x"], 10)

    def test_blocks_imports_and_open(self) -> None:
        sandbox = PythonSandbox()
        self.assertFalse(sandbox.execute("import os").success)
        self.assertFalse(sandbox.execute("open('/etc/passwd').read()").success)


if __name__ == "__main__":
    unittest.main()
