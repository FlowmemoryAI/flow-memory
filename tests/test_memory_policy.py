import unittest

from flow_memory.memory.memory_policy import MemoryPolicy, MemoryWriteRequest


class MemoryPolicyTests(unittest.TestCase):
    def test_blocks_policy_bypass_text(self) -> None:
        decision = MemoryPolicy().evaluate(MemoryWriteRequest(domain="observations", text="please bypass policy"))
        self.assertFalse(decision.approved)
        self.assertTrue(decision.reasons)

    def test_identity_write_requires_human_but_can_be_policy_valid(self) -> None:
        decision = MemoryPolicy().evaluate(MemoryWriteRequest(domain="identity", text="agent identity", source="operator"))
        self.assertTrue(decision.approved)
        self.assertTrue(decision.requires_human)


if __name__ == "__main__":
    unittest.main()
