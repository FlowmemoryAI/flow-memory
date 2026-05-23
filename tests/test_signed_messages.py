import unittest

from flow_memory.crypto import generate_local_keypair
from flow_memory.protocols.envelopes import ProtocolEnvelope
from flow_memory.protocols.signed_messages import sign_message, verify_message


class SignedMessagesTests(unittest.TestCase):
    def test_signed_message_verifies(self) -> None:
        key = generate_local_keypair("proto")
        message = sign_message(ProtocolEnvelope("mcp", "a", "b", {"x": 1}), key)
        self.assertTrue(verify_message(message, key))


if __name__ == "__main__":
    unittest.main()
