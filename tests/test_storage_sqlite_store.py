import unittest

from flow_memory.storage import SQLiteStore


class StorageSQLiteStoreTests(unittest.TestCase):
    def test_put_get_and_schema(self) -> None:
        store = SQLiteStore()
        store.put("agents", "a", {"name": "alpha"})
        record = store.get("agents", "a")
        self.assertIsNotNone(record)
        assert record is not None
        self.assertEqual(record["name"], "alpha")
        self.assertTrue(store.conn.execute("select version from schema_version").fetchone())


if __name__ == "__main__":
    unittest.main()
