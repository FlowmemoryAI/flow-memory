import unittest

from flow_memory.protocols.protocol_manifest import protocol_manifest


class ProtocolManifestTests(unittest.TestCase):
    def test_manifest_lists_protocols(self) -> None:
        names = [item["name"] for item in protocol_manifest()["protocols"]]
        self.assertIn("mcp", names)
        self.assertIn("a2a", names)
        self.assertIn("libp2p", names)


if __name__ == "__main__":
    unittest.main()
