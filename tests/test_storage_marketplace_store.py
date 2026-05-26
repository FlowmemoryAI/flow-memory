import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from flow_memory.storage import MarketplaceStore, SQLiteStore


class StorageMarketplaceStoreTests(unittest.TestCase):
    def test_marketplace_state_persists(self) -> None:
        with TemporaryDirectory() as tmp:
            path = Path(tmp) / "db.sqlite"
            market = MarketplaceStore(SQLiteStore(path))
            market.save_task("t", {"status": "open"})
            task = MarketplaceStore(SQLiteStore(path)).load_task("t")
            self.assertIsNotNone(task)
            assert task is not None
            self.assertEqual(task["status"], "open")


if __name__ == "__main__":
    unittest.main()
