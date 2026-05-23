import json
import subprocess
import sys
import unittest
from pathlib import Path

from flow_memory.release import decide_release_readiness


class ReleaseReadinessTests(unittest.TestCase):
    def test_local_release_candidate_passes_when_gates_pass(self) -> None:
        root = Path(__file__).resolve().parents[1]
        decision = decide_release_readiness(root, target="local")

        self.assertTrue(decision.ok, decision.as_record())
        self.assertEqual("local_release_candidate", decision.classification)
        self.assertFalse(decision.blockers)
        self.assertIn("dependency_inventory", decision.required_evidence)

    def test_production_release_is_blocked_honestly(self) -> None:
        root = Path(__file__).resolve().parents[1]
        decision = decide_release_readiness(root, target="production")

        self.assertFalse(decision.ok)
        self.assertEqual("blocked_production_release", decision.classification)
        self.assertIn("contracts_unaudited", decision.blockers)
        self.assertIn("hardened_sandbox_evidence", decision.required_evidence)


    def test_public_alpha_fails_without_clean_clone_evidence(self) -> None:
        root = Path(__file__).resolve().parents[1]
        clean_clone = root / "release_evidence" / "clean_clone_validation.json"
        if clean_clone.exists():
            self.skipTest("clean clone evidence exists in this checkout")
        decision = decide_release_readiness(root, target="public-alpha")

        self.assertFalse(decision.ok)
        self.assertIn("clean_clone_validation_missing", decision.blockers)
        self.assertIn("base_sepolia_artifacts", decision.required_evidence)

    def test_release_decision_script(self) -> None:
        root = Path(__file__).resolve().parents[1]
        completed = subprocess.run(
            [sys.executable, "scripts/release_decision.py", "--root", str(root), "--target", "local"],
            cwd=root,
            check=True,
            capture_output=True,
            text=True,
        )

        payload = json.loads(completed.stdout)
        self.assertTrue(payload["ok"])
        self.assertEqual("local", payload["target"])
        self.assertIn("dependency_inventory", payload["required_evidence"])

    def test_release_decision_script_accepts_public_alpha_target(self) -> None:
        root = Path(__file__).resolve().parents[1]
        completed = subprocess.run(
            [
                sys.executable,
                "scripts/release_decision.py",
                "--root",
                str(root),
                "--target",
                "public-alpha",
            ],
            cwd=root,
            capture_output=True,
            text=True,
        )

        payload = json.loads(completed.stdout)
        self.assertEqual("public-alpha", payload["target"])
        self.assertIn("clean_clone_validation", payload["required_evidence"])

    def test_release_decision_script_fails_closed_for_production(self) -> None:
        root = Path(__file__).resolve().parents[1]
        completed = subprocess.run(
            [sys.executable, "scripts/release_decision.py", "--root", str(root), "--target", "production"],
            cwd=root,
            capture_output=True,
            text=True,
        )

        payload = json.loads(completed.stdout)
        self.assertNotEqual(0, completed.returncode)
        self.assertFalse(payload["ok"])


if __name__ == "__main__":
    unittest.main()
