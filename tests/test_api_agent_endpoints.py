import unittest

from flow_memory.api.router import create_default_router
from flow_memory.swarm import AgentCard


class ApiAgentEndpointTests(unittest.TestCase):
    def test_agent_endpoints(self) -> None:
        router = create_default_router()
        router.register_agent(AgentCard(did="did:flow:a", name="A", capabilities=("research",)))
        self.assertEqual(router.dispatch("GET", "/agents/did:flow:a")["agent"]["name"], "A")
        self.assertEqual(router.dispatch("POST", "/agents/did:flow:a/run", {"goal": "x"})["status"], "accepted_local_run")


if __name__ == "__main__":
    unittest.main()
