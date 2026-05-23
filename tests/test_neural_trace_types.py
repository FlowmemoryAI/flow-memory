from flow_memory.neural.traces import AgentTrace, PlanTrace, SkillTrace


def test_agent_trace_is_json_record():
    trace = AgentTrace("a1", "healthy", "goal", PlanTrace("goal", ("skill",), True), skills=(SkillTrace("skill", True, 0.9),))
    record = trace.as_record()
    assert record["agent_id"] == "a1"
    assert record["skills"][0]["quality_score"] == 0.9
