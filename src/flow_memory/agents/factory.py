"""Agent factory helpers."""

from __future__ import annotations

from flow_memory.agents.profile import AgentProfile, RiskBudget
from flow_memory.flowlang.parser import parse_flowlang_file
from flow_memory.ir.agent_adapter import agent_profile_from_ir


def create_agent_profile(
    name: str,
    *,
    identity: str = "",
    goals: tuple[str, ...] = (),
    capabilities: tuple[str, ...] = (),
    allowed_skills: tuple[str, ...] = (),
    autonomy_mode: str = "supervised",
    max_spend: float = 0.0,
) -> AgentProfile:
    return AgentProfile(
        name=name,
        identity=identity,
        goals=goals,
        capabilities=capabilities,
        allowed_skills=allowed_skills,
        autonomy_mode=autonomy_mode,
        risk_budget=RiskBudget(max_spend=max_spend, max_escrow_exposure=max_spend, max_slashing_exposure=max_spend),
    )


def create_agent_profile_from_flow(path: str) -> AgentProfile:
    return agent_profile_from_ir(parse_flowlang_file(path))
