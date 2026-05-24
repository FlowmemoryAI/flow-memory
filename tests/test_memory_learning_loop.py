from flow_memory.agents import AgentProfile, AgentRunner
from flow_memory.learning.memory_learning import MemoryLearningStore
from flow_memory.learning.trace_collector import TraceCollector


def test_memory_learning_retrieves_related_trace():
    profile = AgentProfile(name="memory", identity="did:flow:memory", allowed_tools=("observe_environment", "respond"), autonomy_mode="autonomous_local")
    result = AgentRunner(profile).run_cycle("Investigate safety incident")
    trace = TraceCollector().collect(agent_id=profile.agent_id, goal="Investigate safety incident", result_record=result.as_record())
    store = MemoryLearningStore()
    store.add_trace(trace)
    retrieved = store.retrieve("safety incident")
    assert len(retrieved) == 1
    assert store.report()["trace_count"] == 1
