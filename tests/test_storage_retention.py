import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from flow_memory.storage import RetentionPolicy, RetentionRule, SQLiteStore, apply_retention_policy


class StorageRetentionTests(unittest.TestCase):
    def test_prunes_unprotected_table_by_id_order(self) -> None:
        store = SQLiteStore()
        for index in range(5):
            store.put("memory_records", f"record-{index}", {"record_id": f"record-{index}", "value": index})

        report = apply_retention_policy(store, RetentionPolicy(rules=(RetentionRule("memory_records", 2),)))

        self.assertTrue(report.ok)
        self.assertEqual(2, store.count("memory_records"))
        self.assertEqual(("record-3", "record-4"), store.ids("memory_records"))
        self.assertEqual(("record-0", "record-1", "record-2"), report.table_results[0].deleted_ids)

    def test_protected_table_is_skipped_without_explicit_permission(self) -> None:
        store = SQLiteStore()
        for index in range(3):
            store.put("audit_events", f"audit-{index}", {"audit_id": f"audit-{index}"})

        report = apply_retention_policy(store, RetentionPolicy(rules=(RetentionRule("audit_events", 1),)))

        self.assertTrue(report.ok)
        self.assertEqual(3, store.count("audit_events"))
        self.assertTrue(report.table_results[0].skipped)

    def test_protected_table_can_be_pruned_when_explicit(self) -> None:
        store = SQLiteStore()
        for index in range(3):
            store.put("audit_events", f"audit-{index}", {"audit_id": f"audit-{index}"})

        report = apply_retention_policy(store, RetentionPolicy(rules=(RetentionRule("audit_events", 1),), allow_protected_prune=True))

        self.assertTrue(report.ok)
        self.assertEqual(1, store.count("audit_events"))

    def test_retention_script(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(__file__).resolve().parents[1]
            db_path = Path(tmp) / "retention.sqlite3"
            policy_path = Path(tmp) / "policy.json"
            store = SQLiteStore(db_path)
            for index in range(4):
                store.put("memory_records", f"record-{index}", {"record_id": f"record-{index}"})
            policy_path.write_text(json.dumps({"rules": [{"table": "memory_records", "max_rows": 2}]}), encoding="utf-8")

            completed = subprocess.run(
                [sys.executable, "scripts/apply_retention_policy.py", "--db", str(db_path), "--policy", str(policy_path)],
                cwd=root,
                check=True,
                capture_output=True,
                text=True,
            )

            payload = json.loads(completed.stdout)
            self.assertTrue(payload["ok"])
            self.assertEqual(2, SQLiteStore(db_path).count("memory_records"))


if __name__ == "__main__":
    unittest.main()
