import unittest

from flow_memory.swarm import AgentCard, AgentDiscoveryRegistry


class SwarmDiscoveryTests(unittest.TestCase):
    def test_discovers_by_capability(self) -> None:
        registry = AgentDiscoveryRegistry()
        registry.register(AgentCard("did:a", "alpha", ("research",), reputation=2))
        registry.register(AgentCard("did:b", "beta", ("verify",), reputation=1))
        self.assertEqual(registry.discover("research")[0].did, "did:a")


if __name__ == "__main__":
    unittest.main()
