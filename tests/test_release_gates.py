import json
import subprocess
import sys
import unittest
from pathlib import Path

from flow_memory.release import run_release_gates


class ReleaseGateTests(unittest.TestCase):
    def test_release_gates_pass_for_repo(self) -> None:
        root = Path(__file__).resolve().parents[1]
        report = run_release_gates(root)

        self.assertTrue(report.ok, report.as_record())
        self.assertEqual({"api_snapshot", "audit_replay", "base_dry_run", "storage_schema", "secret_scan"}, {result.name for result in report.results})

    def test_release_gate_script_outputs_json(self) -> None:
        root = Path(__file__).resolve().parents[1]
        completed = subprocess.run(
            [sys.executable, "scripts/release_gate.py", "--root", str(root)],
            check=True,
            capture_output=True,
            text=True,
        )

        payload = json.loads(completed.stdout)
        self.assertTrue(payload["ok"])


if __name__ == "__main__":
    unittest.main()
