import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from flow_memory.release import build_dependency_inventory, write_dependency_inventory


class ReleaseDependencyInventoryTests(unittest.TestCase):
    def test_inventory_covers_python_dashboard_and_rust(self) -> None:
        root = Path(__file__).resolve().parents[1]
        inventory = build_dependency_inventory(root)

        self.assertIn("python", inventory.manifests)
        self.assertIn("dashboard", inventory.manifests)
        self.assertIn("rust", inventory.manifests)
        self.assertEqual("flow-memory", inventory.manifests["python"]["name"])
        self.assertIn("dev", inventory.manifests["python"]["optional_dependencies"])
        self.assertEqual("flow-memory-core", inventory.manifests["rust"]["name"])
        self.assertTrue(inventory.inventory_hash)

    def test_write_inventory_round_trip_json(self) -> None:
        root = Path(__file__).resolve().parents[1]
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "dependencies.json"
            write_dependency_inventory(root, path)
            payload = json.loads(path.read_text(encoding="utf-8"))

        self.assertEqual("flow-memory", payload["manifests"]["python"]["name"])

    def test_export_dependency_inventory_script(self) -> None:
        root = Path(__file__).resolve().parents[1]
        completed = subprocess.run(
            [sys.executable, "scripts/export_dependency_inventory.py", "--root", str(root)],
            cwd=root,
            check=True,
            capture_output=True,
            text=True,
        )

        payload = json.loads(completed.stdout)
        self.assertIn("inventory_hash", payload)
        self.assertIn("python", payload["manifests"])


if __name__ == "__main__":
    unittest.main()
