import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from flow_memory.storage import SQLiteStore, compare_store_to_backup, create_backup, write_backup


class StorageIntegrityTests(unittest.TestCase):
    def test_compare_store_to_backup_accepts_matching_state(self) -> None:
        store = SQLiteStore()
        store.put("agents", "agent-1", {"agent_id": "agent-1"})
        backup = json.loads(json.dumps(create_backup(store)))

        report = compare_store_to_backup(store, backup)

        self.assertTrue(report.ok)
        self.assertEqual(report.live_root_hash, report.backup_root_hash)

    def test_compare_store_to_backup_rejects_live_drift(self) -> None:
        store = SQLiteStore()
        store.put("agents", "agent-1", {"agent_id": "agent-1"})
        backup = json.loads(json.dumps(create_backup(store)))
        store.put("agents", "agent-2", {"agent_id": "agent-2"})

        report = compare_store_to_backup(store, backup)

        self.assertFalse(report.ok)
        self.assertIn("root hash mismatch", report.errors)

    def test_verify_storage_backup_script(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(__file__).resolve().parents[1]
            db_path = Path(tmp) / "store.sqlite3"
            backup_path = Path(tmp) / "backup.json"
            store = SQLiteStore(db_path)
            store.put("agents", "agent-1", {"agent_id": "agent-1"})
            write_backup(store, backup_path)

            completed = subprocess.run(
                [sys.executable, "scripts/verify_storage_backup.py", "--db", str(db_path), "--backup", str(backup_path)],
                cwd=root,
                check=True,
                capture_output=True,
                text=True,
            )

            payload = json.loads(completed.stdout)
            self.assertTrue(payload["ok"])


if __name__ == "__main__":
    unittest.main()
