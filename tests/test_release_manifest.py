import json
import subprocess
import sys
import unittest
from pathlib import Path

from flow_memory.crypto.keys import generate_local_keypair
from flow_memory.release import build_release_manifest, verify_release_manifest


class ReleaseManifestTests(unittest.TestCase):
    def test_release_manifest_contains_gates_and_hash(self) -> None:
        root = Path(__file__).resolve().parents[1]
        manifest = build_release_manifest(root)

        self.assertTrue(manifest.release_gates["ok"], manifest.release_gates)
        self.assertEqual("flow-memory-release-manifest-v1", manifest.format)
        self.assertTrue(verify_release_manifest(manifest))

    def test_signed_manifest_rejects_tamper(self) -> None:
        root = Path(__file__).resolve().parents[1]
        key = generate_local_keypair("release-test")
        manifest = build_release_manifest(root, signing_key=key)
        record = dict(manifest.as_record())
        record["git_commit"] = "forged"

        self.assertTrue(verify_release_manifest(manifest, key))
        self.assertFalse(verify_release_manifest(record, key))

    def test_generate_release_manifest_script_outputs_json(self) -> None:
        root = Path(__file__).resolve().parents[1]
        completed = subprocess.run(
            [sys.executable, "scripts/generate_release_manifest.py", "--root", str(root), "--sign-local"],
            cwd=root,
            check=True,
            capture_output=True,
            text=True,
        )

        payload = json.loads(completed.stdout)
        self.assertEqual("flow-memory-release-manifest-v1", payload["format"])
        self.assertTrue(payload["release_gates"]["ok"])
        self.assertIn("signature", payload)


if __name__ == "__main__":
    unittest.main()
