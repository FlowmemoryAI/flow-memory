import unittest

from flow_memory.crypto import ProvenanceChain


class ProvenanceHashesTests(unittest.TestCase):
    def test_hash_chain_verifies_and_detects_tamper(self) -> None:
        chain = ProvenanceChain()
        chain.append({"event": "a"})
        chain.append({"event": "b"})
        self.assertTrue(chain.verify())
        chain.entries[1] = type(chain.entries[1])(1, {"event": "tampered"}, chain.entries[1].previous_hash, chain.entries[1].entry_hash)
        self.assertFalse(chain.verify())


if __name__ == "__main__":
    unittest.main()
