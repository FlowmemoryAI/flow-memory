"""Skill manifest contracts for local/offline Flow Memory skills."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping


_ALLOWED_RISK_LEVELS = frozenset({"low", "medium", "high", "critical"})


def _string_tuple(values: object, field_name: str) -> tuple[str, ...]:
    if values is None:
        return ()
    if not isinstance(values, (tuple, list, set, frozenset)):
        raise ValueError(f"{field_name} must be a sequence of strings")
    result = tuple(values)
    if any(not isinstance(value, str) or not value.strip() for value in result):
        raise ValueError(f"{field_name} must contain only non-empty strings")
    return result


@dataclass(frozen=True, init=False)
class SkillManifest:
    """Static metadata and safety envelope for a runnable skill.

    Schemas intentionally use plain mappings rather than a JSON Schema dependency. The
    runner supports a small deterministic subset for local validation: object, string,
    integer, number, boolean, array, required, properties, and additionalProperties.
    """

    id: str
    name: str
    description: str
    input_schema: Mapping[str, Any] = field(default_factory=dict)
    output_schema: Mapping[str, Any] = field(default_factory=dict)
    permissions: tuple[str, ...] = field(default_factory=tuple)
    schedule: Mapping[str, Any] = field(default_factory=dict)
    economic_value: float = 0.0
    required_capabilities: tuple[str, ...] = field(default_factory=tuple)
    risk_level: str = "low"

    def __init__(
        self,
        id: str | None = None,
        name: str = "",
        description: str = "",
        input_schema: Mapping[str, Any] | None = None,
        output_schema: Mapping[str, Any] | None = None,
        permissions: object = None,
        schedule: Mapping[str, Any] | None = None,
        economic_value: float = 0.0,
        required_capabilities: object = None,
        risk_level: str = "low",
        skill_id: str | None = None,
    ) -> None:
        manifest_id = id if id is not None else skill_id
        object.__setattr__(self, "id", manifest_id or "")
        object.__setattr__(self, "name", name)
        object.__setattr__(self, "description", description)
        object.__setattr__(self, "input_schema", dict(input_schema or {}))
        object.__setattr__(self, "output_schema", dict(output_schema or {}))
        object.__setattr__(self, "permissions", _string_tuple(permissions, "permissions"))
        object.__setattr__(self, "schedule", dict(schedule or {}))
        object.__setattr__(self, "economic_value", float(economic_value))
        object.__setattr__(
            self,
            "required_capabilities",
            _string_tuple(required_capabilities, "required_capabilities"),
        )
        object.__setattr__(self, "risk_level", risk_level)
        errors = self.validate()
        if errors:
            raise ValueError("; ".join(errors))

    @property
    def skill_id(self) -> str:
        """Compatibility alias for code that follows Flow Memory's domain-id style."""

        return self.id

    def validate(self) -> tuple[str, ...]:
        errors: list[str] = []
        if not self.id.strip():
            errors.append("id is required")
        if not self.name.strip():
            errors.append("name is required")
        if not self.description.strip():
            errors.append("description is required")
        if not isinstance(self.input_schema, Mapping):
            errors.append("input_schema must be a mapping")
        if not isinstance(self.output_schema, Mapping):
            errors.append("output_schema must be a mapping")
        if not isinstance(self.schedule, Mapping):
            errors.append("schedule must be a mapping")
        if self.economic_value < 0:
            errors.append("economic_value must be non-negative")
        if self.risk_level not in _ALLOWED_RISK_LEVELS:
            errors.append(f"risk_level must be one of {sorted(_ALLOWED_RISK_LEVELS)}")
        return tuple(errors)

    def as_record(self) -> Mapping[str, Any]:
        return {
            "id": self.id,
            "skill_id": self.skill_id,
            "name": self.name,
            "description": self.description,
            "input_schema": dict(self.input_schema),
            "output_schema": dict(self.output_schema),
            "permissions": tuple(self.permissions),
            "schedule": dict(self.schedule),
            "economic_value": self.economic_value,
            "required_capabilities": tuple(self.required_capabilities),
            "risk_level": self.risk_level,
        }
