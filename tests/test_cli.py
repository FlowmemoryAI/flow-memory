import io
import json
import unittest
from pathlib import Path
from contextlib import redirect_stdout

from flow_memory.cli import main


class CLITests(unittest.TestCase):
    def _run_cli(self, argv: list[str]) -> tuple[int, str]:
        buf = io.StringIO()
        with redirect_stdout(buf):
            code = main(argv)
        return code, buf.getvalue()

    def test_module_shorthand_runs_json(self) -> None:
        code, output = self._run_cli(["--json", "Explore and report"])
        self.assertEqual(code, 0)
        payload = json.loads(output)
        self.assertIn("cycle_id", payload)
        self.assertTrue(payload["action_result"]["success"])

    def test_run_subcommand_runs(self) -> None:
        code, output = self._run_cli(["run", "Explore and report"])
        self.assertEqual(code, 0)
        self.assertIn("Processed goal", output)

    def test_verify_script_uses_portable_python_launcher(self) -> None:
        verify_script = (Path(__file__).resolve().parents[1] / "scripts" / "verify.sh").read_text(
            encoding="utf-8"
        )
        self.assertIn("python3", verify_script)
        self.assertIn("py -3", verify_script)
        self.assertNotIn("python -m pytest", verify_script)


if __name__ == "__main__":
    unittest.main()
