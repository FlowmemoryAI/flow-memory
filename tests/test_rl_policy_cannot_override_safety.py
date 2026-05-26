from flow_memory.agents.profile import AgentProfile
from flow_memory.agents.runner import AgentRunner

def test_rl_suggestion_does_not_override_policy_block() -> None:
    profile=AgentProfile(name="blocked", autonomy_mode="manual", rl_config={"enabled": True, "training_envs": ["safety_gate"]})
    result=AgentRunner(profile).run_cycle("transfer funds through marketplace")
    assert result.requires_approval is True
    assert result.output["rl"]["enabled"] is True
    assert result.accepted is False
