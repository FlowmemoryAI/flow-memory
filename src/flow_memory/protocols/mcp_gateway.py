"""MCP gateway seam."""

class McpGatewayNotConfigured(RuntimeError):
    pass


class McpGateway:
    def call(self, _tool: str, _payload: dict):
        raise McpGatewayNotConfigured("MCP gateway transport is not configured")
