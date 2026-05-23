import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from flow_memory.storage import SQLiteStore, export_jsonl


class StorageExportTests(unittest.TestCase):
    def test_jsonl_export_works(self) -> None:
        with TemporaryDirectory() as tmp:
            store = SQLiteStore()
            store.put("audit_events", "a", {"kind": "audit"})
            output = export_jsonl(store, "audit_events", Path(tmp) / "audit.jsonl")
            self.assertIn("audit", output.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
