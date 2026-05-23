"""FlowIR compiler helpers."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any, Mapping

from flow_memory.ir.agent import AgentSpec


@dataclass(frozen=True)
class CompileResult:
    """Result of compiling a source declaration into a manifest."""

    agent: AgentSpec | None
    manifest: Mapping[str, Any] = field(default_factory=dict)
    errors: tuple[str, ...] = field(default_factory=tuple)
    warnings: tuple[str, ...] = field(default_factory=tuple)

    @property
    def ok(self) -> bool:
        return not self.errors and self.agent is not None

    def to_json(self, *, indent: int | None = 2) -> str:
        return json.dumps(self.as_record(), indent=indent, sort_keys=True)

    def as_record(self) -> Mapping[str, Any]:
        return {
            "ok": self.ok,
            "manifest": _json_safe(self.manifest),
            "errors": tuple(self.errors),
            "warnings": tuple(self.warnings),
        }


def compile_agent(agent: AgentSpec) -> CompileResult:
    """Validate an AgentSpec and produce a JSON-serializable manifest."""

    errors = agent.validate()
    manifest = agent.as_manifest() if not errors else {}
    return CompileResult(agent=agent if not errors else None, manifest=manifest, errors=errors)


def manifest_json(agent: AgentSpec, *, indent: int | None = 2) -> str:
    """Return a JSON manifest or raise ValueError if validation fails."""

    result = compile_agent(agent)
    if result.errors:
        raise ValueError("; ".join(result.errors))
    return json.dumps(_json_safe(result.manifest), indent=indent, sort_keys=True)


def _json_safe(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, tuple):
        return [_json_safe(item) for item in value]
    if isinstance(value, list):
        return [_json_safe(item) for item in value]
    return value
