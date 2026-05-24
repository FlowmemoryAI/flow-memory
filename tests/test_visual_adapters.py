from flow_memory.visualization.adapters import (
    agent_participants_to_visual_events,
    audit_records_to_visual_events,
    economy_records_to_visual_events,
    memory_records_to_visual_events,
    neural_record_to_visual_events,
    rl_record_to_visual_events,
    safety_record_to_visual_events,
)


def test_visual_adapters_emit_typed_events():
    events = []
    events += list(agent_participants_to_visual_events(({"role": "worker", "card": {"did": "did:flow:w", "name": "Worker", "capabilities": ("work",), "reputation": 3.0}},)))
    events += list(economy_records_to_visual_events(({"task_id": "task-1", "status": "settled", "amount": 2.0, "requester_id": "did:flow:r", "worker_id": "did:flow:w"},)))
    events += list(memory_records_to_visual_events(({"record_id": "m1", "summary": "remember", "importance": 0.7},)))
    events += list(neural_record_to_visual_events({"backend": "tiny_torch", "status": "skipped", "plan_scores": [{"total_score": 0.8}]}))
    events += list(rl_record_to_visual_events({"env_id": "safety_gate", "metrics": {"mean_reward": 2.0, "mean_success_rate": 1.0}}))
    events += list(safety_record_to_visual_events({"decision_id": "gate-1", "approved": True, "risk_level": "low"}))
    events += list(audit_records_to_visual_events(({"event": "completed", "actor": "did:flow:w"},)))
    types = {event.event_type for event in events}
    assert {"agent", "task", "economy", "memory", "neural", "rl", "safety", "audit"} <= types
    assert all(event.provenance == "live" for event in events)
