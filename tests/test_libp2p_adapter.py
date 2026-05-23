import unittest

from flow_memory.protocols.libp2p_adapter import Libp2pAdapter, Libp2pNotConfigured


class Libp2pAdapterTests(unittest.TestCase):
    def test_libp2p_unconfigured(self) -> None:
        with self.assertRaises(Libp2pNotConfigured):
            Libp2pAdapter().publish("topic", b"payload")


if __name__ == "__main__":
    unittest.main()
