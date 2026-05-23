import unittest

from flow_memory.swarm import AgentCard, ReputationRouter


class SwarmCoalitionTests(unittest.TestCase):
    def test_reputation_router_prefers_best_agent(self) -> None:
        router = ReputationRouter()
        low = AgentCard("did:low", "low", ("research",), reputation=1)
        high = AgentCard("did:high", "high", ("research",), reputation=5)
        self.assertEqual(router.choose((low, high), "research").did, "did:high")


if __name__ == "__main__":
    unittest.main()
