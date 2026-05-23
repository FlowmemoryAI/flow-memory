import unittest

from flow_memory.agents import create_agent_profile
from flow_memory.crypto import generate_local_keypair, sign_payload, verify_payload


class AgentProfileSignatureTests(unittest.TestCase):
    def test_agent_profile_signature(self) -> None:
        profile = create_agent_profile("signed")
        key = generate_local_keypair("agent")
        signature = sign_payload(profile.as_record(), key)
        self.assertTrue(verify_payload(profile.as_record(), signature, key))


if __name__ == "__main__":
    unittest.main()
