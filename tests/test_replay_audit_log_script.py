import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from flow_memory.storage import AuditStore, SQLiteStore


class ReplayAuditLogScriptTests(unittest.TestCase):
    def test_script_replays_and_checkpoints_chained_audit_log(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "audit.sqlite3"
            audit = AuditStore(SQLiteStore(db_path))
            audit.append_chained({"event": "started", "agent_id": "agent-1"})
            audit.append_chained({"event": "completed", "agent_id": "agent-1", "success": True})

            completed = subprocess.run(
                [
                    sys.executable,
                    "scripts/replay_audit_log.py",
                    "--db",
                    str(db_path),
                    "--checkpoint",
                    "--require-events",
                ],
                check=True,
                capture_output=True,
                text=True,
            )

            payload = json.loads(completed.stdout)
            self.assertTrue(payload["ok"])
            self.assertEqual(2, len(payload["records"]))
            self.assertIn("checkpoint", payload)


if __name__ == "__main__":
    unittest.main()
