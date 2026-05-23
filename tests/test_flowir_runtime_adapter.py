import unittest

from flow_memory.agents import create_agent_profile
from flow_memory.ir.runtime_adapter import runtime_for_agent


class FlowIRRuntimeAdapterTests(unittest.TestCase):
    def test_runtime_for_agent_starts_managers(self) -> None:
        runtime = runtime_for_agent(create_agent_profile("runtime"))
        self.assertEqual(runtime.health_summary()["status"], "ok")


if __name__ == "__main__":
    unittest.main()
