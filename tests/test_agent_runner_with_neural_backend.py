from flow_memory.agents.profile import AgentProfile
from flow_memory.agents.runner import AgentRunner


def test_agent_runner_attaches_neural_metadata():
    profile = AgentProfile(name="n", allowed_tools=("respond",), neural_config={"backend": "none"})
    result = AgentRunner(profile).run_cycle("Explore and report")
    assert result.output["neural"]["backend"] == "none"
