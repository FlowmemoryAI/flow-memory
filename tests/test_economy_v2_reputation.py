import unittest

from flow_memory.economy import AgentEconomyV2


class EconomyV2ReputationTests(unittest.TestCase):
    def test_reputation_is_did_bound_and_non_transferable(self) -> None:
        economy = AgentEconomyV2()
        reputation = economy.reputation_for("did:agent:1")
        reputation.record({"event": "win"}, 2.0)
        self.assertEqual(economy.reputation_for("did:agent:1").score, 2.0)
        self.assertFalse(hasattr(reputation, "transfer"))


if __name__ == "__main__":
    unittest.main()
