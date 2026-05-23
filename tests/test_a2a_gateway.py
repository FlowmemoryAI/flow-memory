import unittest

from flow_memory.protocols.a2a_gateway import A2AGateway, A2AGatewayNotConfigured


class A2AGatewayTests(unittest.TestCase):
    def test_a2a_gateway_unconfigured(self) -> None:
        with self.assertRaises(A2AGatewayNotConfigured):
            A2AGateway().send({})


if __name__ == "__main__":
    unittest.main()
