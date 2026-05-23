import unittest

from flow_memory.storage import ReputationStore, SQLiteStore


class StorageReputationStoreTests(unittest.TestCase):
    def test_reputation_updates_persist(self) -> None:
        store = ReputationStore(SQLiteStore())
        store.save_update("u", {"agent": "a", "delta": 1})
        self.assertEqual(store.list_updates()[0]["delta"], 1)


if __name__ == "__main__":
    unittest.main()
