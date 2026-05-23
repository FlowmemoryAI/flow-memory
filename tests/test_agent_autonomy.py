import unittest

from flow_memory.agents import decide_autonomy


class AgentAutonomyTests(unittest.TestCase):
    def test_autonomy_modes_gate_actions(self) -> None:
        self.assertTrue(decide_autonomy("autonomous_local", risk_level="low").allowed)
        self.assertTrue(decide_autonomy("manual", risk_level="low").requires_approval)
        self.assertTrue(decide_autonomy("autonomous_economic", economic_value=5, max_spend=1).requires_approval)
        self.assertFalse(decide_autonomy("disabled").allowed)


if __name__ == "__main__":
    unittest.main()
