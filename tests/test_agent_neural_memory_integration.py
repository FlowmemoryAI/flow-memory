from flow_memory.agents.neural_binding import AgentNeuralBinding
from flow_memory.agents.profile import AgentProfile
from flow_memory.agents.planner import CognitivePlanner


def test_agent_neural_binding_adds_memory_scores() -> None:
    profile = AgentProfile(name="n", allowed_tools=("respond",), neural_config={"backend": "none"})
    plan = CognitivePlanner().create_plan("summarize safety memory")
    metadata = AgentNeuralBinding().annotate_plan(profile, "summarize safety memory", plan, ("safety memory",))
    assert metadata["memory_retrieval_scores"]
