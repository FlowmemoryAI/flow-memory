"""FlowIR skill adapters."""

from __future__ import annotations

from flow_memory.ir.skill import SkillSpec
from flow_memory.skills import SkillManifest


def skill_manifest_from_ir(skill: SkillSpec) -> SkillManifest:
    return SkillManifest(
        id=skill.id,
        name=skill.id.replace("-", " ").title(),
        description=skill.description or "FlowIR declared skill",
        permissions=skill.permission_names(),
        input_schema=skill.inputs_schema,
        output_schema=skill.outputs_schema,
        risk_level=skill.risk_level,
    )
