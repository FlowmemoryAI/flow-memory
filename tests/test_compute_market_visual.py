from flow_memory.compute_market import compute_marketplace_plan
from flow_memory.visualization.adapters.compute_adapter import compute_record_to_visual_events
from flow_memory.visualization.reducer import reduce_visual_events
from flow_memory.visualization.schemas import visual_schema


def test_compute_visual_schema_and_reducer_path():
    record = compute_marketplace_plan({"task": {"task_id": "visual-compute"}, "policy": {"max_total_cost": 0.01, "max_quote": 0.01, "dry_run_required": True}})
    events = compute_record_to_visual_events(record, agent_id="did:flow:compute")
    state = reduce_visual_events(events, provenance="replay")

    assert "compute" in visual_schema()["event_types"]
    assert state.compute
    assert state.compute[0].agent_id == "did:flow:compute"
    assert any(item.event == "route_decision_selected" for item in state.compute)
    assert all(item.dry_run_only and item.no_funds_moved for item in state.compute)


def test_compute_fail_closed_visual_event():
    record = compute_marketplace_plan({"task": {"task_id": "visual-denied"}, "policy": {"max_total_cost": 0.0, "max_quote": 0.0, "dry_run_required": True}})
    events = compute_record_to_visual_events(record, agent_id="did:flow:compute")
    state = reduce_visual_events(events)

    assert record["ok"] is False
    assert state.compute[0].event == "policy_denied_fail_closed"
    assert state.compute[0].status
