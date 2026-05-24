from flow_memory.neural.live import NeuralRuntimeManager, neural_live_config_from_mapping


def test_neural_live_session_step_and_learning_are_deterministic():
    manager = NeuralRuntimeManager()
    config = {
        "enabled": True,
        "backend": "tiny_torch",
        "live_mode": True,
        "policy_fallback": "allow_non_neural",
        "learning_enabled": True,
        "seed": 42,
    }
    first = manager.create_session("agent-a", config)
    second = manager.create_session("agent-a", config)

    first_step = manager.run_step(first.session_id, {"goal": "Explore and report", "plan_id": "p"})
    second_step = manager.run_step(second.session_id, {"goal": "Explore and report", "plan_id": "p"})

    assert first_step["ok"] is True
    assert second_step["ok"] is True
    assert first_step["local_only"] is True
    assert first_step["external_model_calls"] is False
    assert first_step["plan_score"] == second_step["plan_score"]
    assert first_step["prediction_confidence"] == second_step["prediction_confidence"]

    learning = manager.learn(first.session_id, {"outcome": "success"})
    assert learning["status"] == "learned"
    assert learning["after_metric"] <= learning["before_metric"]

    checkpoint = manager.checkpoint(first.session_id)
    assert checkpoint["metadata_only"] is True
    assert checkpoint["raw_weights_written"] is False


def test_neural_live_fail_closed_when_backend_unavailable_and_policy_requires_it():
    manager = NeuralRuntimeManager()
    session = manager.create_session(
        "agent-b",
        {"enabled": True, "backend": "tiny_torch", "live_mode": True, "policy_fallback": "fail_closed"},
    )
    step = manager.run_step(session.session_id, {"goal": "unsafe action"})

    # In environments with torch installed, tiny_torch is available and the step is allowed.
    # Without torch, the same config fails closed instead of silently acting.
    if session.backend_available:
        assert step["ok"] is True
    else:
        assert step["ok"] is False
        assert step["status"] == "fail_closed"
        assert step["policy_gate_state"] == "denied"


def test_neural_live_config_parses_options_and_streams():
    config = neural_live_config_from_mapping({
        "backend": "tiny_torch",
        "live_mode": True,
        "options": {"policy_fallback": "allow_non_neural"},
        "perception_streams": ["text", "memory"],
    })

    assert config.enabled is True
    assert config.live_mode is True
    assert config.policy_fallback == "allow_non_neural"
    assert config.perception_streams == ("text", "memory")
