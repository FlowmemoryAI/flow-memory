from flow_memory.agents.profile import AgentProfile, RiskBudget
from flow_memory.agents.runner import AgentRunner


def test_neural_metadata_does_not_bypass_economic_approval():
    profile = AgentProfile(
        name="n",
        identity="did:flow:n",
        allowed_skills=("economic-task",),
        autonomy_mode="supervised",
        risk_budget=RiskBudget(max_spend=100),
        neural_config={"backend": "none"},
    )
    result = AgentRunner(profile).run_cycle("settle marketplace escrow")
    assert result.requires_approval is True
    assert result.accepted is False
    assert result.output["neural"]["safety_authority"] == "policy_engine_and_approval_gate"
