from flow_memory.visualization.adapters.neural_adapter import neural_record_to_visual_events
from flow_memory.visualization.reducer import reduce_visual_events


def test_visual_reducer_preserves_neural_live_embodiment_fields():
    record = {
        "agent_id": "agent-1",
        "backend": "tiny_torch",
        "status": "ok",
        "session_id": "session-1",
        "live_step": {
            "session_id": "session-1",
            "agent_id": "agent-1",
            "backend": "tiny_torch",
            "status": "ok",
            "phase": "learning",
            "plan_score": 0.8,
            "risk_score": 0.2,
            "surprise_score": 0.1,
            "prediction_confidence": 0.9,
            "uncertainty": 0.1,
            "learning_tick_count": 3,
            "memory_activation_count": 2,
            "action_state": "recommended",
            "policy_gate_state": "pending_policy_gate",
        },
    }

    state = reduce_visual_events(neural_record_to_visual_events(record, agent_id="agent-1", provenance="replay"), provenance="replay").as_record()
    signal = state["neural"][0]

    assert signal["session_id"] == "session-1"
    assert signal["phase"] == "learning"
    assert signal["prediction_confidence"] == 0.9
    assert signal["learning_tick_count"] == 3
    assert signal["action_state"] == "recommended"
    assert signal["policy_gate_state"] == "pending_policy_gate"
