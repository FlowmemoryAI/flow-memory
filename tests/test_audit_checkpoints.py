import unittest

from flow_memory.crypto.keys import generate_local_keypair
from flow_memory.storage import AuditStore, SQLiteStore, create_audit_checkpoint, verify_audit_checkpoint


class AuditCheckpointTests(unittest.TestCase):
    def test_signed_checkpoint_verifies_against_replay_result(self) -> None:
        key = generate_local_keypair("audit-test")
        audit = AuditStore(SQLiteStore())
        audit.append_chained({"event": "started", "agent_id": "agent-1"})
        audit.append_chained({"event": "completed", "agent_id": "agent-1", "success": True})
        replay = audit.verify_chained()

        checkpoint = create_audit_checkpoint(replay, key)

        self.assertTrue(
            verify_audit_checkpoint(
                checkpoint,
                key,
                expected_latest_hash=replay.latest_hash,
                expected_event_count=len(replay.records),
            )
        )

    def test_checkpoint_rejects_tampered_latest_hash(self) -> None:
        key = generate_local_keypair("audit-test")
        audit = AuditStore(SQLiteStore())
        audit.append_chained({"event": "started"})
        replay = audit.verify_chained()
        checkpoint = create_audit_checkpoint(replay, key).as_record()
        checkpoint["latest_hash"] = "forged"

        self.assertFalse(verify_audit_checkpoint(checkpoint, key))


if __name__ == "__main__":
    unittest.main()
