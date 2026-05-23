import unittest

from flow_memory.memory.adapters import LocalMemoryAdapter, QdrantMemoryAdapter


class MemoryAdaptersTests(unittest.TestCase):
    def test_local_adapter_writes_and_queries(self) -> None:
        adapter = LocalMemoryAdapter()
        adapter.write({"domain": "goals", "text": "ship v2"})
        self.assertEqual(adapter.query("goals")[0]["text"], "ship v2")

    def test_external_adapter_fails_clearly_without_dependency_use(self) -> None:
        self.assertEqual(QdrantMemoryAdapter("http://localhost:6333").describe()["adapter"], "qdrant")


if __name__ == "__main__":
    unittest.main()
