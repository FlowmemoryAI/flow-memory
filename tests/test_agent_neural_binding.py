from flow_memory.agents.neural_binding import AgentNeuralBinding
from flow_memory.agents.profile import AgentProfile
from flow_memory.agents.planner import CognitivePlanner


def test_agent_neural_binding_tiny_torch_skips_without_torch() -> None:
    profile = AgentProfile(name="n", neural_config={"backend": "tiny_torch"})
    plan = CognitivePlanner().create_plan("Explore and report")
    metadata = AgentNeuralBinding().annotate_plan(profile, "Explore and report", plan)
    assert metadata["backend"] == "tiny_torch"
    assert metadata["safety_authority"] == "policy_engine_and_approval_gate"
