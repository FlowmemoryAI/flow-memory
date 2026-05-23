import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from flow_memory.release import export_release_evidence, verify_release_evidence


class ReleaseEvidenceTests(unittest.TestCase):
    def test_export_and_verify_release_evidence_bundle(self) -> None:
        root = Path(__file__).resolve().parents[1]
        with tempfile.TemporaryDirectory() as tmp:
            bundle = export_release_evidence(root, Path(tmp) / "evidence")
            verified = verify_release_evidence(Path(tmp) / "evidence")

            self.assertEqual(bundle.index["bundle_hash"], verified.index["bundle_hash"])
            self.assertIn("release_manifest.json", bundle.index["files"])
            self.assertIn("dependency_inventory.json", bundle.index["files"])

    def test_verify_release_evidence_detects_tamper(self) -> None:
        root = Path(__file__).resolve().parents[1]
        with tempfile.TemporaryDirectory() as tmp:
            evidence = Path(tmp) / "evidence"
            export_release_evidence(root, evidence)
            manifest_path = evidence / "release_manifest.json"
            payload = json.loads(manifest_path.read_text(encoding="utf-8"))
            payload["git_commit"] = "forged"
            manifest_path.write_text(json.dumps(payload), encoding="utf-8")

            with self.assertRaises(ValueError):
                verify_release_evidence(evidence)

    def test_export_release_evidence_script(self) -> None:
        root = Path(__file__).resolve().parents[1]
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "evidence"
            completed = subprocess.run(
                [sys.executable, "scripts/export_release_evidence.py", "--root", str(root), "--out", str(out)],
                cwd=root,
                check=True,
                capture_output=True,
                text=True,
            )
            verify_completed = subprocess.run(
                [sys.executable, "scripts/export_release_evidence.py", "--out", str(out), "--verify-only"],
                cwd=root,
                check=True,
                capture_output=True,
                text=True,
            )

            self.assertTrue(json.loads(completed.stdout)["ok"])
            self.assertTrue(json.loads(verify_completed.stdout)["ok"])


if __name__ == "__main__":
    unittest.main()
