import unittest

from flow_memory.swarm import DelegationContract


class SwarmDelegationTests(unittest.TestCase):
    def test_delegation_lifecycle(self) -> None:
        contract = DelegationContract("did:delegator", "did:delegate", "research", "brief", 1.0)
        contract.assign({"topic": "agents"})
        contract.complete({"brief": "done"})
        contract.verify(True, {"reviewer": "did:verifier"})
        self.assertEqual(contract.status, "verified")


if __name__ == "__main__":
    unittest.main()
