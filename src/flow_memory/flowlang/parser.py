"""Dependency-free FlowLang v0 parser.

FlowLang v0 intentionally uses a strict, line-oriented subset instead of a full
parser generator. The syntax is designed to be readable by humans, easy to emit
from tools, and straightforward to compile into FlowIR dataclasses.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from flow_memory.ir import AgentSpec, EconomicSpec, MemorySpec, PermissionSpec, PlanSpec, PolicySpec, SkillSpec


class FlowLangParseError(ValueError):
    """Raised when FlowLang source is syntactically invalid."""


def parse_flowlang_file(path: str | Path) -> AgentSpec:
    return parse_flowlang(Path(path).read_text(encoding="utf-8"))


def parse_flowlang(source: str) -> AgentSpec:
    """Parse FlowLang v0 source into an AgentSpec.

    Supported top-level forms:

    - `agent NAME`
    - `identity DID`
    - `belief TEXT`
    - `goal TEXT`
    - `memory:` block
    - `economy:` block
    - `policy NAME:` block
    - `skill NAME:` block
    - `plan NAME:` block
    """

    agent_name = ""
    identity = ""
    beliefs: list[str] = []
    goals: list[str] = []
    memory_data: dict[str, Any] = {}
    economy_data: dict[str, Any] = {}
    policies: list[PolicySpec] = []
    skills: list[SkillSpec] = []
    plans: list[PlanSpec] = []

    current_kind = ""
    current_name = ""
    current_data: dict[str, Any] = {}

    def flush_current() -> None:
        nonlocal current_kind, current_name, current_data, memory_data, economy_data
        if not current_kind:
            return
        if current_kind == "memory":
            memory_data.update(current_data)
        elif current_kind == "economy":
            economy_data.update(current_data)
        elif current_kind == "policy":
            policies.append(_policy_from_data(current_name, current_data))
        elif current_kind == "skill":
            skills.append(_skill_from_data(current_name, current_data))
        elif current_kind == "plan":
            plans.append(_plan_from_data(current_name, current_data))
        else:
            raise FlowLangParseError(f"unknown block kind: {current_kind}")
        current_kind = ""
        current_name = ""
        current_data = {}

    for line_number, raw_line in enumerate(source.splitlines(), start=1):
        stripped = _strip_comment(raw_line).strip()
        if not stripped:
            continue
        is_indented = raw_line[:1].isspace()
        if is_indented:
            if not current_kind:
                raise FlowLangParseError(f"line {line_number}: indented field without a block")
            key, value = _split_field(stripped, line_number)
            current_data[key] = _parse_value(value)
            continue

        flush_current()
        if stripped.endswith(":"):
            header = stripped[:-1].strip()
            parts = header.split(maxsplit=1)
            kind = parts[0]
            if kind in {"memory", "economy"} and len(parts) == 1:
                current_kind = kind
                current_name = kind
                current_data = {}
                continue
            if kind in {"policy", "skill", "plan"} and len(parts) == 2:
                current_kind = kind
                current_name = parts[1].strip()
                if not current_name:
                    raise FlowLangParseError(f"line {line_number}: {kind} name is required")
                current_data = {}
                continue
            raise FlowLangParseError(f"line {line_number}: unknown block header {header!r}")

        key, value = _split_top_level(stripped, line_number)
        if key == "agent":
            agent_name = str(_parse_value(value))
        elif key == "identity":
            identity = str(_parse_value(value))
        elif key == "belief":
            beliefs.append(str(_parse_value(value)))
        elif key == "goal":
            goals.append(str(_parse_value(value)))
        else:
            raise FlowLangParseError(f"line {line_number}: unknown top-level directive {key!r}")

    flush_current()
    return AgentSpec(
        name=agent_name,
        identity=identity,
        memory=_memory_from_data(memory_data),
        beliefs=tuple(beliefs),
        goals=tuple(goals),
        policies=tuple(policies),
        skills=tuple(skills),
        plans=tuple(plans),
        economy=_economy_from_data(economy_data),
    )


def _strip_comment(line: str) -> str:
    in_quote = False
    quote_char = ""
    for index, char in enumerate(line):
        if char in {'"', "'"}:
            if not in_quote:
                in_quote = True
                quote_char = char
            elif quote_char == char:
                in_quote = False
                quote_char = ""
        elif char == "#" and not in_quote:
            return line[:index]
    return line


def _split_top_level(line: str, line_number: int) -> tuple[str, str]:
    if ":" in line:
        prefix = line.split(":", 1)[0]
        if not any(char.isspace() for char in prefix):
            return _split_field(line, line_number)
    parts = line.split(maxsplit=1)
    if len(parts) != 2:
        raise FlowLangParseError(f"line {line_number}: expected `key value`")
    return parts[0], parts[1]


def _split_field(line: str, line_number: int) -> tuple[str, str]:
    if ":" not in line:
        raise FlowLangParseError(f"line {line_number}: expected `key: value`")
    key, value = line.split(":", 1)
    key = key.strip().replace("-", "_")
    if not key:
        raise FlowLangParseError(f"line {line_number}: empty field name")
    return key, value.strip()


def _parse_value(value: str) -> Any:
    value = value.strip()
    if value == "":
        return ""
    if value.startswith("[") and value.endswith("]"):
        inner = value[1:-1].strip()
        if not inner:
            return []
        return [_parse_value(item.strip()) for item in inner.split(",")]
    if (value.startswith('"') and value.endswith('"')) or (value.startswith("'") and value.endswith("'")):
        return value[1:-1]
    lowered = value.lower()
    if lowered == "true":
        return True
    if lowered == "false":
        return False
    if lowered in {"none", "null"}:
        return None
    try:
        return int(value)
    except ValueError:
        pass
    try:
        return float(value)
    except ValueError:
        return value


def _memory_from_data(data: dict[str, Any]) -> MemorySpec:
    return MemorySpec(
        working_capacity=int(data.get("working_capacity", 7)),
        episodic=_as_bool(data.get("episodic", True)),
        semantic=_as_bool(data.get("semantic", True)),
        procedural=_as_bool(data.get("procedural", True)),
        economic=_as_bool(data.get("economic", False)),
        adapters=_as_string_tuple(data.get("adapters", ("local",))),
        metadata=_metadata(data, {"working_capacity", "episodic", "semantic", "procedural", "economic", "adapters"}),
    )


def _economy_from_data(data: dict[str, Any]) -> EconomicSpec:
    return EconomicSpec(
        settlement=str(data.get("settlement", "none")),
        budget=float(data.get("budget", 0.0) or 0.0),
        currency=str(data.get("currency", "LOCAL")),
        marketplace=str(data.get("marketplace", "local")),
        allow_slashing=_as_bool(data.get("allow_slashing", False)),
        metadata=_metadata(data, {"settlement", "budget", "currency", "marketplace", "allow_slashing"}),
    )


def _policy_from_data(name: str, data: dict[str, Any]) -> PolicySpec:
    return PolicySpec(
        id=name,
        permissions=_as_string_tuple(data.get("permissions", ())),
        risk_level=str(data.get("risk_level", data.get("risk", "low"))),
        requires_approval=_as_bool(data.get("requires_approval", False)),
        allow_unsafe=_as_bool(data.get("allow_unsafe", False)),
        metadata=_metadata(data, {"permissions", "risk_level", "risk", "requires_approval", "allow_unsafe"}),
    )


def _skill_from_data(name: str, data: dict[str, Any]) -> SkillSpec:
    permissions = tuple(PermissionSpec(name=permission) for permission in _as_string_tuple(data.get("permissions", ())))
    return SkillSpec(
        id=name,
        description=str(data.get("description", "")),
        permissions=permissions,
        risk_level=str(data.get("risk_level", data.get("risk", "low"))),
        inputs_schema=dict(data.get("inputs_schema", {}) if isinstance(data.get("inputs_schema", {}), dict) else {}),
        outputs_schema=dict(data.get("outputs_schema", {}) if isinstance(data.get("outputs_schema", {}), dict) else {}),
        wasm_component=str(data.get("wasm_component", "")),
        metadata=_metadata(data, {"description", "permissions", "risk_level", "risk", "inputs_schema", "outputs_schema", "wasm_component"}),
    )


def _plan_from_data(name: str, data: dict[str, Any]) -> PlanSpec:
    return PlanSpec(
        id=name,
        steps=_as_string_tuple(data.get("steps", data.get("requires", ()))),
        goal=str(data.get("goal", "")),
        risk_level=str(data.get("risk_level", data.get("risk", "low"))),
        metadata=_metadata(data, {"steps", "requires", "goal", "risk_level", "risk"}),
    )


def _as_string_tuple(value: Any) -> tuple[str, ...]:
    if value is None:
        return ()
    if isinstance(value, str):
        if not value.strip():
            return ()
        return tuple(item.strip() for item in value.split(",") if item.strip())
    if isinstance(value, (list, tuple, set, frozenset)):
        return tuple(str(item).strip() for item in value if str(item).strip())
    return (str(value),)


def _as_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "on"}
    return bool(value)


def _metadata(data: dict[str, Any], known: set[str]) -> dict[str, Any]:
    return {key: value for key, value in data.items() if key not in known}
