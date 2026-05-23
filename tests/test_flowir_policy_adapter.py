import unittest

from flow_memory.ir import PolicySpec
from flow_memory.ir.policy_adapter import policy_rule_from_ir


class FlowIRPolicyAdapterTests(unittest.TestCase):
    def test_policy_maps_to_rule(self) -> None:
        rule = policy_rule_from_ir(PolicySpec(id="p", permissions=("respond",)))
        self.assertEqual(rule["id"], "p")
        self.assertIn("respond", rule["permissions"])


if __name__ == "__main__":
    unittest.main()
