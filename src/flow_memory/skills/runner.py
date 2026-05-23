"""Local skill runner with safety policy checks."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Callable, Mapping

from flow_memory.core.types import Plan, PlanStep, PolicyDecision
from flow_memory.safety.system import SafetySystem
from flow_memory.skills.manifest import SkillManifest
from flow_memory.skills.registry import SkillRegistry

SkillHandler = Callable[[Mapping[str, Any]], Any]


@dataclass(frozen=True)
class SkillRunResult:
    skill_id: str
    success: bool
    output: Any = None
    error: str | None = None
    policy_decision: PolicyDecision | None = None


@dataclass
class SkillRunner:
    """Runs registered local handlers after schema and safety checks."""

    registry: SkillRegistry
    safety: SafetySystem = field(default_factory=SafetySystem)
    handlers: dict[str, SkillHandler] = field(default_factory=dict)

    def register_handler(self, skill_id: str, handler: SkillHandler) -> None:
        self.registry.get(skill_id)
        self.handlers[skill_id] = handler

    def run(self, skill_id: str, payload: Mapping[str, Any]) -> SkillRunResult:
        manifest = self.registry.get(skill_id)
        handler = self.handlers.get(skill_id)
        if handler is None:
            raise KeyError(f"No local handler registered for skill: {skill_id}")
        validation_errors = _validate_schema(payload, manifest.input_schema, "input")
        if validation_errors:
            raise ValueError("; ".join(validation_errors))

        plan = _plan_for_manifest(manifest)
        decision = self.safety.approve(plan)
        self.safety.audit.append(
            {
                "kind": "skill_run_requested",
                "skill_id": skill_id,
                "input": dict(payload),
                "decision": asdict(decision),
            }
        )
        if not decision.approved:
            result = SkillRunResult(skill_id=skill_id, success=False, error="; ".join(decision.reasons), policy_decision=decision)
            self.safety.record_action_result(plan, {"success": False, "error": result.error or "Skill policy denied"})
            return result

        try:
            output = handler(dict(payload))
            output_errors = _validate_schema(output, manifest.output_schema, "output")
            if output_errors:
                raise ValueError("; ".join(output_errors))
        except Exception as exc:  # local runner boundary: convert handler errors into audited results
            result = SkillRunResult(skill_id=skill_id, success=False, error=str(exc), policy_decision=decision)
            self.safety.record_action_result(plan, {"success": False, "error": str(exc)})
            self.safety.audit.append({"kind": "skill_run_completed", "skill_id": skill_id, "success": False, "error": str(exc)})
            return result

        result = SkillRunResult(skill_id=skill_id, success=True, output=output, policy_decision=decision)
        self.safety.record_action_result(plan, {"success": True, "output": output})
        self.safety.audit.append({"kind": "skill_run_completed", "skill_id": skill_id, "success": True, "output": output})
        return result


def _plan_for_manifest(manifest: SkillManifest) -> Plan:
    permissions = manifest.permissions or ("respond",)
    approval_required = manifest.risk_level in {"high", "critical"}
    steps = tuple(
        PlanStep(
            action=f"skill.run:{manifest.skill_id}",
            required_permission=permission,
            approval_required=approval_required,
            economic_value=manifest.economic_value,
        )
        for permission in permissions
    )
    return Plan(
        goal=f"Run skill {manifest.skill_id}",
        steps=steps,
        metadata={
            "skill_id": manifest.skill_id,
            "risk_level": manifest.risk_level,
            "required_capabilities": tuple(manifest.required_capabilities),
        },
    )


def _validate_schema(value: Any, schema: Mapping[str, Any], path: str) -> tuple[str, ...]:
    if not schema:
        return ()
    errors: list[str] = []
    expected_type = schema.get("type")
    if expected_type is not None and not _matches_type(value, str(expected_type)):
        return (f"{path} must be {expected_type}",)

    if expected_type == "object" or "properties" in schema or "required" in schema:
        if not isinstance(value, Mapping):
            return (f"{path} must be object",)
        required = schema.get("required", ())
        if not isinstance(required, (tuple, list)):
            errors.append(f"{path}.required must be a list")
        else:
            for key in required:
                if key not in value:
                    errors.append(f"{path}.{key} is required")
        properties = schema.get("properties", {})
        if not isinstance(properties, Mapping):
            errors.append(f"{path}.properties must be an object")
        else:
            for key, child_schema in properties.items():
                if key in value:
                    if not isinstance(child_schema, Mapping):
                        errors.append(f"{path}.{key} schema must be an object")
                    else:
                        errors.extend(_validate_schema(value[key], child_schema, f"{path}.{key}"))
        if schema.get("additionalProperties") is False and isinstance(properties, Mapping):
            allowed = set(properties)
            for key in value:
                if key not in allowed:
                    errors.append(f"{path}.{key} is not allowed")

    if expected_type == "array":
        if not isinstance(value, (tuple, list)):
            return (f"{path} must be array",)
        item_schema = schema.get("items")
        if isinstance(item_schema, Mapping):
            for index, item in enumerate(value):
                errors.extend(_validate_schema(item, item_schema, f"{path}[{index}]"))

    return tuple(errors)


def _matches_type(value: Any, expected_type: str) -> bool:
    if expected_type == "object":
        return isinstance(value, Mapping)
    if expected_type == "array":
        return isinstance(value, (tuple, list))
    if expected_type == "string":
        return isinstance(value, str)
    if expected_type == "integer":
        return isinstance(value, int) and not isinstance(value, bool)
    if expected_type == "number":
        return isinstance(value, (int, float)) and not isinstance(value, bool)
    if expected_type == "boolean":
        return isinstance(value, bool)
    if expected_type == "null":
        return value is None
    return True
