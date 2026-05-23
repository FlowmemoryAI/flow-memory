import unittest

from flow_memory.protocols.envelopes import ProtocolEnvelope
from flow_memory.protocols.routing import route_for


class ProtocolEnvelopeTests(unittest.TestCase):
    def test_envelope_serializes_and_routes(self) -> None:
        envelope = ProtocolEnvelope("a2a", "a", "b", {"hello": "world"})
        self.assertEqual(route_for(envelope), "a2a")
        self.assertEqual(envelope.as_record()["payload"]["hello"], "world")


if __name__ == "__main__":
    unittest.main()
