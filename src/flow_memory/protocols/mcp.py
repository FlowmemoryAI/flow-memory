"""MCP-compatible tool metadata helpers."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping

from flow_memory.action.tools import Tool, ToolRegistry


@dataclass(frozen=True)
class MCPToolSpec:
    name: str
    description: str
    input_schema: Mapping[str, Any] = field(default_factory=dict)
    required_permission: str = "tool.invoke"

    def as_dict(self) -> Mapping[str, Any]:
        return {
            "name": self.name,
            "description": self.description,
            "input_schema": dict(self.input_schema),
            "required_permission": self.required_permission,
        }


@dataclass
class MCPToolServer:
    """Transport-agnostic MCP-style server wrapper for local tools."""

    registry: ToolRegistry

    def list_tools(self) -> tuple[Mapping[str, Any], ...]:
        return tuple(tool_to_mcp_spec(tool).as_dict() for tool in self.registry.list())

    def call_tool(self, name: str, args: Mapping[str, Any]) -> Any:
        return self.registry.call(name, args)


def tool_to_mcp_spec(tool: Tool) -> MCPToolSpec:
    return MCPToolSpec(
        name=tool.name,
        description=tool.description,
        input_schema=tool.input_schema,
        required_permission=tool.required_permission,
    )



def registry_to_mcp_manifest(registry: ToolRegistry) -> Mapping[str, Any]:
    return {
        "protocol": "mcp-compatible",
        "tools": [tool_to_mcp_spec(tool).as_dict() for tool in registry.list()],
    }


def registry_to_mcp_manifest(registry: ToolRegistry) -> Mapping[str, Any]:
    """Return a transport-neutral MCP-compatible manifest for a tool registry."""

    return {
        "protocol": "mcp-compatible",
        "tools": [tool_to_mcp_spec(tool).as_dict() for tool in registry.list()],
    }
