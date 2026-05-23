import unittest

from flow_memory.agents import create_agent_profile
from flow_memory.agents.memory_binding import AgentMemoryBinding
from flow_memory.ir.runtime_adapter import runtime_summary


class AgentBindingsTests(unittest.TestCase):
    def test_memory_binding_and_runtime_summary(self) -> None:
        memory = AgentMemoryBinding()
        memory.write("note", {"text": "hello"})
        self.assertTrue(memory.load_context("hello"))
        summary = runtime_summary(create_agent_profile("bound"))
        self.assertEqual(summary["runtime"]["status"], "ok")


if __name__ == "__main__":
    unittest.main()
