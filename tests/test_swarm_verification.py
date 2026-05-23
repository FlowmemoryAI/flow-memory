import unittest

from flow_memory.swarm import MultiAgentVerifier, VerificationVote


class SwarmVerificationTests(unittest.TestCase):
    def test_multi_agent_verifier_threshold(self) -> None:
        verifier = MultiAgentVerifier(threshold=2)
        first = verifier.submit("task1", VerificationVote("did:v1", True))
        second = verifier.submit("task1", VerificationVote("did:v2", True))
        self.assertFalse(first["accepted"])
        self.assertTrue(second["accepted"])


if __name__ == "__main__":
    unittest.main()
