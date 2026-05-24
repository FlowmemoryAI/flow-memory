from flow_memory.visualization import reduce_visual_events, visual_event


def test_visual_event_reducer_builds_network_state():
    state = reduce_visual_events(
        (
            visual_event("agent", "did:flow:worker", {"agent_id": "did:flow:worker", "label": "Worker", "role": "worker", "reputation": 7.0}),
            visual_event("task", "task-1", {"task_id": "task-1", "label": "Task", "status": "settled", "requester_id": "did:flow:requester", "worker_id": "did:flow:worker", "reward": 3.0}),
            visual_event("economy", "ledger-1", {"edge_id": "ledger-1", "from_id": "did:flow:requester", "to_id": "did:flow:worker", "amount": 3.0, "status": "settled"}),
            visual_event("safety", "gate-1", {"gate_id": "gate-1", "agent_id": "did:flow:worker", "decision": "approved"}),
        )
    )
    record = state.as_record()
    assert record["runtime"]["agents"] == 1
    assert record["runtime"]["tasks"] == 1
    assert record["tasks"][0]["status"] == "settled"
    assert record["economy"][0]["amount"] == 3.0
    assert record["safety"][0]["decision"] == "approved"
