import unittest

from flow_memory.protocols.mcp_gateway import McpGateway, McpGatewayNotConfigured


class McpGatewayTests(unittest.TestCase):
    def test_mcp_gateway_unconfigured(self) -> None:
        with self.assertRaises(McpGatewayNotConfigured):
            McpGateway().call("tool", {})


if __name__ == "__main__":
    unittest.main()
