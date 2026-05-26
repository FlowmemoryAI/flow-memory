"""Adapters from FlowIR AgentSpec to AgentProfile."""

from __future__ import annotations

from flow_memory.agents.profile import AgentProfile, RiskBudget
from flow_memory.ir.agent import AgentSpec


def agent_profile_from_ir(agent: AgentSpec) -> AgentProfile:
    errors = agent.validate()
    if errors:
        raise ValueError("; ".join(errors))
    autonomy_mode = str(agent.metadata.get("autonomy_mode", "supervised"))
    max_spend = float(agent.metadata.get("risk_budget", agent.economy.budget))
    return AgentProfile(
        name=agent.name,
        identity=agent.identity,
        description=str(agent.metadata.get("description", "FlowIR declared agent")),
        persona=str(agent.metadata.get("persona", "")),
        goals=tuple(agent.goals),
        constraints=tuple(str(item) for item in agent.metadata.get("constraints", ())),
        capabilities=tuple(str(item) for item in agent.metadata.get("capabilities", (skill.id for skill in agent.skills))),
        allowed_tools=tuple(str(item) for item in agent.metadata.get("allowed_tools", ("respond",))),
        allowed_skills=tuple(skill.id for skill in agent.skills),
        memory_config=agent.memory.as_manifest(),
        economy_config=agent.economy.as_manifest(),
        neural_config=dict(agent.metadata.get("neural", {})),
        rl_config=dict(agent.metadata.get("rl", {})),
        compute_config=dict(agent.metadata.get("compute_market", {})),
        cognition_config=dict(agent.metadata.get("cognition", {})),
        autonomy_mode=autonomy_mode,
        risk_budget=RiskBudget(max_spend=max_spend, max_escrow_exposure=max_spend, max_slashing_exposure=max_spend),
        metadata={"flowir": agent.as_manifest()},
    )
