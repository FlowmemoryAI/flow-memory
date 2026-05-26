"""MCP gateway seam."""
from collections.abc import Mapping


class McpGatewayNotConfigured(RuntimeError):
    pass


class McpGateway:
    def call(self, _tool: str, _payload: Mapping[str, object]) -> Mapping[str, object]:
        raise McpGatewayNotConfigured("MCP gateway transport is not configured")
