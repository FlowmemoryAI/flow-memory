from flow_memory.agents.profile import AgentProfile
from flow_memory.agents.rl_binding import AgentRlBinding

def test_agent_rl_binding_returns_advisory_suggestion():
    profile=AgentProfile(name="rl", rl_config={"enabled": True, "training_envs": ["safety_gate"]})
    suggestion=AgentRlBinding().suggest(profile, "do safe work")
    assert suggestion["enabled"] is True
    assert suggestion["safety_authority"] == "policy_engine_and_approval_gate"
