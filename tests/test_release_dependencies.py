import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from flow_memory.release import (
    build_dependency_inventory,
    validate_dependency_policy,
    write_dependency_inventory,
)


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

    def test_dependency_policy_accepts_current_manifests(self) -> None:
        root = Path(__file__).resolve().parents[1]
        report = validate_dependency_policy(root)

        self.assertTrue(report.ok, report.as_record())
        self.assertTrue(report.inventory_hash)
        self.assertFalse(report.errors)

    def test_dependency_policy_rejects_unpinned_optional_dependency(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "dashboard").mkdir()
            (root / "rust" / "flow-memory-core").mkdir(parents=True)
            (root / "pyproject.toml").write_text(
                "[project]\nname = \"flow-memory\"\nversion = \"0.0.0\"\ndependencies = []\n"
                "[project.optional-dependencies]\ndev = [\"pytest\"]\n",
                encoding="utf-8",
            )
            (root / "dashboard" / "package.json").write_text(
                json.dumps(
                    {"name": "@flow-memory/dashboard", "version": "0.0.0", "private": True}
                ),
                encoding="utf-8",
            )
            (root / "rust" / "flow-memory-core" / "Cargo.toml").write_text(
                "[package]\n"
                "name = \"flow-memory-core\"\n"
                "version = \"0.1.0\"\n"
                "edition = \"2021\"\n",
                encoding="utf-8",
            )

            report = validate_dependency_policy(root)

        self.assertFalse(report.ok)
        self.assertTrue(
            any("explicit version constraint" in error for error in report.errors)
        )

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

    def test_export_dependency_inventory_policy_script(self) -> None:
        root = Path(__file__).resolve().parents[1]
        completed = subprocess.run(
            [
                sys.executable,
                "scripts/export_dependency_inventory.py",
                "--root",
                str(root),
                "--policy",
            ],
            cwd=root,
            check=True,
            capture_output=True,
            text=True,
        )

        payload = json.loads(completed.stdout)
        self.assertTrue(payload["ok"])
        self.assertIn("inventory_hash", payload)


if __name__ == "__main__":
    unittest.main()
