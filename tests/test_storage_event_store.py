import unittest

from flow_memory.storage import EventStore, SQLiteStore


class StorageEventStoreTests(unittest.TestCase):
    def test_events_persist(self) -> None:
        events = EventStore(SQLiteStore())
        event_id = events.append({"kind": "tick"})
        self.assertEqual(events.list()[0]["event_id"], event_id)


if __name__ == "__main__":
    unittest.main()
