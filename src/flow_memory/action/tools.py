"""Tool registry with typed permission boundaries."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping

from flow_memory.core.types import ToolHandler
from flow_memory.exceptions import ToolNotFound


@dataclass(frozen=True)
class Tool:
    name: str
    description: str
    handler: ToolHandler
    required_permission: str = "tool.invoke"
    input_schema: Mapping[str, Any] = field(default_factory=dict)
    side_effect_level: str = "none"


@dataclass
class ToolRegistry:
    _tools: dict[str, Tool] = field(default_factory=dict, init=False, repr=False)

    def register(self, tool: Tool) -> None:
        self._tools[tool.name] = tool

    def unregister(self, name: str) -> None:
        self._tools.pop(name, None)

    def get(self, name: str) -> Tool:
        try:
            return self._tools[name]
        except KeyError as exc:
            raise ToolNotFound(f"Tool not found: {name}") from exc

    def _validate(self, tool: Tool, args: Mapping[str, Any]) -> None:
        schema = tool.input_schema or {}
        if schema.get("type") == "object" and not isinstance(args, Mapping):
            raise ValueError("Tool args must be an object")
        required = schema.get("required", [])
        for key in required:
            if key not in args:
                raise ValueError(f"Missing required tool argument: {key}")
        properties = schema.get("properties", {})
        for key, spec in properties.items():
            if key not in args:
                continue
            expected = spec.get("type") if isinstance(spec, Mapping) else None
            if expected == "string" and not isinstance(args[key], str):
                raise ValueError(f"Tool argument {key} must be a string")
            if expected == "number" and not isinstance(args[key], (int, float)):
                raise ValueError(f"Tool argument {key} must be a number")
            if expected == "integer" and not isinstance(args[key], int):
                raise ValueError(f"Tool argument {key} must be an integer")
            if expected == "boolean" and not isinstance(args[key], bool):
                raise ValueError(f"Tool argument {key} must be a boolean")

    def call(self, name: str, args: Mapping[str, Any]) -> Any:
        tool = self.get(name)
        self._validate(tool, args)
        return tool.handler(args)

    def list(self) -> tuple[Tool, ...]:
        return tuple(self._tools.values())

    def manifest(self) -> tuple[Mapping[str, Any], ...]:
        return tuple(
            {
                "name": tool.name,
                "description": tool.description,
                "required_permission": tool.required_permission,
                "input_schema": dict(tool.input_schema),
                "side_effect_level": tool.side_effect_level,
            }
            for tool in self.list()
        )


def _echo(args: Mapping[str, Any]) -> Mapping[str, Any]:
    return {"echo": args.get("message", "")}


def _observe_environment(args: Mapping[str, Any]) -> Mapping[str, Any]:
    entities = args.get("entities", [])
    affordances = args.get("affordances", [])
    return {
        "environment": "local_simulation",
        "observations": [
            "sandbox is active",
            f"tracked_entities={len(entities)}",
            f"affordances={','.join(affordances) if affordances else 'none'}",
        ],
        "risk": "low",
    }


def _capability_manifest(args: Mapping[str, Any]) -> Mapping[str, Any]:
    capabilities = args.get("capabilities", [])
    return {"capabilities": list(capabilities), "format": "flow-memory.capability_manifest.v1"}


def default_tool_registry() -> ToolRegistry:
    registry = ToolRegistry()
    registry.register(
        Tool(
            name="echo",
            description="Return the provided message.",
            handler=_echo,
            required_permission="respond",
            input_schema={"type": "object", "properties": {"message": {"type": "string"}}},
        )
    )
    registry.register(
        Tool(
            name="observe_environment",
            description="Read-only local environment observation.",
            handler=_observe_environment,
            required_permission="environment.observe",
            input_schema={"type": "object"},
            side_effect_level="read",
        )
    )
    registry.register(
        Tool(
            name="capability_manifest",
            description="Return a local capability manifest.",
            handler=_capability_manifest,
            required_permission="tool.invoke",
            input_schema={"type": "object"},
            side_effect_level="none",
        )
    )
    return registry
