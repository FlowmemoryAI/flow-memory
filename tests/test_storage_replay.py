import unittest

from flow_memory.storage import AuditStore, SQLiteStore, replay_events, verify_chained_events


class StorageReplayTests(unittest.TestCase):
    def test_replay_events_builds_deterministic_chain(self) -> None:
        result = replay_events(
            (
                {"event_id": "event-1", "event": "started", "payload": {"goal": "run"}},
                {"event_id": "event-2", "event": "completed", "payload": {"ok": True}},
            )
        )

        self.assertTrue(result.ok)
        self.assertEqual(2, len(result.records))
        self.assertEqual("genesis", result.records[0].previous_hash)
        self.assertEqual(result.records[0].chain_hash, result.records[1].previous_hash)
        self.assertEqual(result.latest_hash, result.records[1].chain_hash)

    def test_replay_events_rejects_duplicate_ids(self) -> None:
        result = replay_events(({"event_id": "same", "event": "a"}, {"event_id": "same", "event": "b"}))

        self.assertFalse(result.ok)
        self.assertIn("duplicate event id", " ".join(result.errors))

    def test_audit_store_chained_events_verify_and_detect_tamper(self) -> None:
        store = SQLiteStore()
        audit = AuditStore(store)
        audit.append_chained({"event": "agent_cycle_started", "agent_id": "agent-1"})
        audit.append_chained({"event": "agent_cycle_completed", "agent_id": "agent-1", "success": True})

        verified = audit.verify_chained()
        self.assertTrue(verified.ok)
        self.assertEqual(2, len(verified.records))

        tampered = [dict(event) for event in audit.list_chained()]
        tampered[0]["event"] = "agent_cycle_forged"
        tamper_result = verify_chained_events(tampered)

        self.assertFalse(tamper_result.ok)
        self.assertIn("payload hash mismatch", " ".join(tamper_result.errors))


if __name__ == "__main__":
    unittest.main()
