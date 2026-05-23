import unittest

from flow_memory.flowlang import parse_flowlang
from flow_memory.flowlang.examples import EXAMPLE_FLOWLANG
from flow_memory.ir.agent_adapter import agent_profile_from_ir


class FlowIRAgentAdapterTests(unittest.TestCase):
    def test_agent_spec_maps_to_profile(self) -> None:
        profile = agent_profile_from_ir(parse_flowlang(EXAMPLE_FLOWLANG))
        self.assertEqual(profile.name, "FlowResearcher")
        self.assertIn("research-brief", profile.allowed_skills)


if __name__ == "__main__":
    unittest.main()
