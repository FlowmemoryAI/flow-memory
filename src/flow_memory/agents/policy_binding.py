"""Agent policy binding."""

from __future__ import annotations

from flow_memory.agents.autonomy import AutonomyDecision, decide_autonomy
from flow_memory.agents.profile import AgentProfile
from flow_memory.agents.planner import Plan


class AgentPolicyBinding:
    def check_plan(self, profile: AgentProfile, plan: Plan) -> AutonomyDecision:
        return decide_autonomy(
            profile.autonomy_mode,
            risk_level=plan.risk_level,
            economic_value=plan.economic_value,
            max_spend=profile.risk_budget.max_spend,
        )
