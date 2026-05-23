"""Protocol adapters for agent interoperability."""

from flow_memory.protocols.a2a import AgentMessage, CapabilityManifest, LocalA2ABus
from flow_memory.protocols.mcp import MCPToolServer, MCPToolSpec, registry_to_mcp_manifest, tool_to_mcp_spec

__all__ = [
    "AgentMessage",
    "CapabilityManifest",
    "LocalA2ABus",
    "MCPToolServer",
    "MCPToolSpec",
    "registry_to_mcp_manifest",
    "registry_to_mcp_manifest",
    "tool_to_mcp_spec",
]
