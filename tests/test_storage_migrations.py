import json
import subprocess
import sys
import unittest
from pathlib import Path

from flow_memory.storage import SQLiteStore, migration_plan, schema_fingerprint, verify_schema


class StorageMigrationTests(unittest.TestCase):
    def test_migration_plan_describes_current_schema(self) -> None:
        plan = migration_plan()

        self.assertEqual(1, plan.current_version)
        self.assertEqual(1, len(plan.steps))
        self.assertEqual(plan.schema_hash, schema_fingerprint())
        self.assertIn("agents", plan.steps[0].creates_tables)

    def test_verify_schema_accepts_migrated_store(self) -> None:
        verification = verify_schema(SQLiteStore())

        self.assertTrue(verification.ok)
        self.assertEqual(1, verification.observed_version)
        self.assertFalse(verification.missing_tables)

    def test_verify_storage_schema_script_outputs_plan(self) -> None:
        root = Path(__file__).resolve().parents[1]
        completed = subprocess.run(
            [sys.executable, "scripts/verify_storage_schema.py"],
            cwd=root,
            check=True,
            capture_output=True,
            text=True,
        )

        payload = json.loads(completed.stdout)
        self.assertTrue(payload["ok"])
        self.assertEqual("initial_local_store", payload["migration_plan"]["steps"][0]["name"])


if __name__ == "__main__":
    unittest.main()
