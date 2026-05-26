from flow_memory.agents import AgentProfile, AgentRunner
from flow_memory.learning.trace_collector import TraceCollector


def test_learning_trace_collector_records_agent_cycle() -> None:
    profile = AgentProfile(name="trace", identity="did:flow:trace", allowed_tools=("observe_environment", "respond"), autonomy_mode="autonomous_local")
    result = AgentRunner(profile).run_cycle("Explore and report")
    collector = TraceCollector()
    trace = collector.collect(agent_id=profile.agent_id, goal="Explore and report", result_record=result.as_record(), rl_reward=1.0)
    assert trace.agent_id == profile.agent_id
    assert trace.success() is True
    assert collector.as_records()[0]["goal"] == "Explore and report"
