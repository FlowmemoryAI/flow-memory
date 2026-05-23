"""FlowIR public contracts."""

from flow_memory.ir.agent import AgentSpec
from flow_memory.ir.compiler import CompileResult, compile_agent, manifest_json
from flow_memory.ir.economy import EconomicSpec
from flow_memory.ir.memory import MemorySpec
from flow_memory.ir.plan import PlanSpec
from flow_memory.ir.policy import PermissionSpec, PolicySpec, RiskLevel, is_unsafe_permission
from flow_memory.ir.skill import SkillSpec

__all__ = [
    "AgentSpec",
    "CompileResult",
    "EconomicSpec",
    "MemorySpec",
    "PermissionSpec",
    "PlanSpec",
    "PolicySpec",
    "RiskLevel",
    "SkillSpec",
    "compile_agent",
    "is_unsafe_permission",
    "manifest_json",
]
