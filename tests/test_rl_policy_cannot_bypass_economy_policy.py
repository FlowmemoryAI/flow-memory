from flow_memory.agents.profile import AgentProfile, RiskBudget
from flow_memory.agents.runner import AgentRunner

def test_rl_suggestion_cannot_bypass_economic_autonomy_controls():
    profile=AgentProfile(name="econ", autonomy_mode="supervised", risk_budget=RiskBudget(max_spend=0), rl_config={"enabled": True, "training_envs": ["economy_market"]})
    result=AgentRunner(profile).run_cycle("perform paid settlement")
    assert result.requires_approval is True
    assert result.output["rl"]["env_id"] == "economy_market"
