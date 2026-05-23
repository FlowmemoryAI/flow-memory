import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from flow_memory.storage import AuditStore, SQLiteStore, evidence_from_jsonl, read_jsonl_events


class AuditReplayEndToEndTests(unittest.TestCase):
    def test_export_replay_restore_success(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(__file__).resolve().parents[1]
            db_path = Path(tmp) / "audit.sqlite3"
            log_path = Path(tmp) / "audit.jsonl"
            restored_path = Path(tmp) / "restored.sqlite3"
            store = SQLiteStore(db_path)
            audit = AuditStore(store)
            audit.append_chained({"event": "agent_registered", "agent_id": "agent-a"})
            audit.append_chained({"event": "task_settled", "task_id": "task-1", "agent_id": "agent-a"})

            exported = subprocess.run(
                [sys.executable, "scripts/export_event_log.py", "--db", str(db_path), "--out", str(log_path)],
                cwd=root,
                check=True,
                capture_output=True,
                text=True,
            )
            export_payload = json.loads(exported.stdout)
            self.assertTrue(export_payload["ok"])
            self.assertEqual(export_payload["evidence"]["event_count"], 2)

            replayed = subprocess.run(
                [sys.executable, "scripts/replay_event_log.py", "--log", str(log_path), "--restore-db", str(restored_path)],
                cwd=root,
                check=True,
                capture_output=True,
                text=True,
            )
            replay_payload = json.loads(replayed.stdout)
            self.assertTrue(replay_payload["ok"])
            self.assertEqual(replay_payload["restored"], 2)
            self.assertEqual(replay_payload["latest_hash"], export_payload["evidence"]["latest_hash"])
            self.assertEqual(len(SQLiteStore(restored_path).list("audit_events")), 2)

    def test_replay_detects_payload_tamper(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(__file__).resolve().parents[1]
            db_path = Path(tmp) / "audit.sqlite3"
            log_path = Path(tmp) / "audit.jsonl"
            store = SQLiteStore(db_path)
            audit = AuditStore(store)
            audit.append_chained({"event": "agent_registered", "agent_id": "agent-a"})
            audit.append_chained({"event": "task_settled", "task_id": "task-1", "agent_id": "agent-a"})
            subprocess.run(
                [sys.executable, "scripts/export_event_log.py", "--db", str(db_path), "--out", str(log_path)],
                cwd=root,
                check=True,
                capture_output=True,
                text=True,
            )

            events = [dict(event) for event in read_jsonl_events(log_path)]
            events[1]["agent_id"] = "attacker"
            log_path.write_text("".join(json.dumps(event, sort_keys=True) + "\n" for event in events), encoding="utf-8")

            replayed = subprocess.run(
                [sys.executable, "scripts/replay_event_log.py", "--log", str(log_path)],
                cwd=root,
                check=False,
                capture_output=True,
                text=True,
            )
            payload = json.loads(replayed.stdout)
            self.assertNotEqual(replayed.returncode, 0)
            self.assertFalse(payload["ok"])
            self.assertIn("payload hash mismatch", "\n".join(payload["errors"]))
            self.assertFalse(evidence_from_jsonl(log_path).replay_ok)


if __name__ == "__main__":
    unittest.main()
