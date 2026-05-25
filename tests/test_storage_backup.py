import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from flow_memory.storage import SQLiteStore, create_backup, restore_backup, validate_backup


class StorageBackupTests(unittest.TestCase):
    def test_backup_restore_round_trip(self) -> None:
        source = SQLiteStore()
        source.put("agents", "agent-1", {"agent_id": "agent-1", "name": "alpha"})
        source.put("audit_events", "audit-1", {"audit_id": "audit-1", "event": "created"})

        bundle = create_backup(source)
        manifest = validate_backup(bundle)
        target = SQLiteStore()
        restored = restore_backup(bundle, target)

        self.assertEqual(manifest.root_hash, restored.root_hash)
        self.assertEqual("alpha", target.get("agents", "agent-1")["name"])
        self.assertEqual("created", target.get("audit_events", "audit-1")["event"])

    def test_restore_refuses_non_empty_target_without_overwrite(self) -> None:
        source = SQLiteStore()
        source.put("agents", "agent-1", {"agent_id": "agent-1"})
        target = SQLiteStore()
        target.put("agents", "existing", {"agent_id": "existing"})

        with self.assertRaises(ValueError):
            restore_backup(create_backup(source), target)

    def test_validate_backup_detects_tamper(self) -> None:
        source = SQLiteStore()
        source.put("agents", "agent-1", {"agent_id": "agent-1", "name": "alpha"})
        bundle = json.loads(json.dumps(create_backup(source)))
        bundle["tables"]["agents"][0]["name"] = "forged"

        with self.assertRaises(ValueError):
            validate_backup(bundle)

    def test_backup_and_restore_scripts(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(__file__).resolve().parents[1]
            source_db = Path(tmp) / "source.sqlite3"
            restored_db = Path(tmp) / "restored.sqlite3"
            backup_path = Path(tmp) / "backup.json"
            source = SQLiteStore(source_db)
            source.put("agents", "agent-1", {"agent_id": "agent-1", "name": "alpha"})

            subprocess.run(
                [sys.executable, "scripts/backup_storage.py", "--db", str(source_db), "--out", str(backup_path)],
                cwd=root,
                check=True,
                capture_output=True,
                text=True,
            )
            completed = subprocess.run(
                [sys.executable, "scripts/restore_storage.py", "--backup", str(backup_path), "--db", str(restored_db)],
                cwd=root,
                check=True,
                capture_output=True,
                text=True,
            )

            payload = json.loads(completed.stdout)
            self.assertTrue(payload["ok"])
            self.assertEqual("alpha", SQLiteStore(restored_db).get("agents", "agent-1")["name"])


if __name__ == "__main__":
    unittest.main()
