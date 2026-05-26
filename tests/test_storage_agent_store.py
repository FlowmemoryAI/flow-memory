import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from flow_memory.storage import AgentStore, SQLiteStore


class StorageAgentStoreTests(unittest.TestCase):
    def test_agent_state_persists_across_reopen(self) -> None:
        with TemporaryDirectory() as tmp:
            path = Path(tmp) / "db.sqlite"
            agents = AgentStore(SQLiteStore(path))
            agents.save_state("a", {"status": "idle"})
            reopened = AgentStore(SQLiteStore(path))
            state = reopened.load_state("a")
            self.assertIsNotNone(state)
            assert state is not None
            self.assertEqual(state["status"], "idle")


if __name__ == "__main__":
    unittest.main()
