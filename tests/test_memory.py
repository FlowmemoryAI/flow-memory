import tempfile
import unittest
from pathlib import Path

from flow_memory.core.types import MemoryRecord
from flow_memory.memory.system import EpisodicMemory, MemorySystem, WorkingMemory


class MemoryTests(unittest.TestCase):
    def test_working_memory_capacity(self) -> None:
        memory = WorkingMemory(capacity=2)
        memory.put(MemoryRecord(kind="test", text="one"))
        memory.put(MemoryRecord(kind="test", text="two"))
        memory.put(MemoryRecord(kind="test", text="three"))
        self.assertEqual([item.text for item in memory.snapshot()], ["two", "three"])

    def test_episodic_retrieval(self) -> None:
        memory = EpisodicMemory()
        memory.record("observation", "the robot navigates through a maze")
        memory.record("observation", "the wallet settles a task")
        results = memory.retrieve("navigation maze", limit=1)
        self.assertEqual(len(results), 1)
        self.assertIn("maze", results[0].text)

    def test_episodic_jsonl_round_trip(self) -> None:
        memory = EpisodicMemory()
        memory.record("observation", "safe agents keep audit logs")
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "memory.jsonl"
            memory.save_jsonl(path)
            loaded = EpisodicMemory()
            loaded.load_jsonl(path)
            self.assertEqual(loaded.timeline()[0].text, "safe agents keep audit logs")

    def test_semantic_consolidation(self) -> None:
        system = MemorySystem()
        from flow_memory.perception import DualStreamPerception

        perception = DualStreamPerception().process("Robot explore and report")
        system.consolidate_perception(perception)
        self.assertTrue(system.semantic.nodes)


if __name__ == "__main__":
    unittest.main()
