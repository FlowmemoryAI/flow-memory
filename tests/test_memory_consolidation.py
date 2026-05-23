import unittest

from flow_memory.memory.consolidation import MemoryConsolidator


class MemoryConsolidationTests(unittest.TestCase):
    def test_consolidates_domains(self) -> None:
        result = MemoryConsolidator().consolidate(({"domain": "goals"}, {"domain": "tasks"}))
        self.assertEqual(result["count"], 2)
        self.assertEqual(result["domains"], ("goals", "tasks"))


if __name__ == "__main__":
    unittest.main()
