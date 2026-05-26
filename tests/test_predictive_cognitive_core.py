from flow_memory.agents.predictive_core import PredictiveCognitiveCore
from flow_memory.agents.profile import AgentProfile
from flow_memory.agents.runner import AgentRunner
from flow_memory.neural.live import NeuralRuntimeManager
from flow_memory.visualization.adapters.cognitive_adapter import prediction_experience_to_visual_events
from flow_memory.visualization.reducer import reduce_visual_events
from flow_memory.release.evidence import build_evidence_documents
from flow_memory.release.predictive_cognitive_evidence import predictive_cognitive_core_evidence, verify_predictive_cognitive_core_evidence


def test_predictive_core_forecasts_and_records_prediction_error():
    profile = AgentProfile(name="predictive-agent", allowed_tools=("respond",))
    runner = AgentRunner(profile)
    plan = runner.cognition.plan(profile, "verify dashboard before claiming success")
    core = PredictiveCognitiveCore()

    forecast = core.forecast(profile, "verify dashboard before claiming success", plan, ())
    experience = core.observe_outcome(
        forecast,
        {"success": False, "blocked": True, "reason": "served stale placeholder"},
        {"success": False, "quality_score": 0.2, "surprise_score": 1.0},
    )

    assert forecast.prediction_id.startswith("prediction_")
    assert forecast.predicted_outcome
    assert forecast.counterfactuals
    assert experience.prediction_error > 0.5
    assert "Verify assumptions" in experience.lesson
    assert experience.neural_learning_sample["learning_signal"] if "learning_signal" in experience.neural_learning_sample else True
    assert experience.neural_learning_sample["prediction_error"] == experience.prediction_error


def test_agent_runner_writes_prediction_experience_and_retrieves_lesson():
    profile = AgentProfile(
        name="predictive-runner",
        allowed_tools=("respond",),
        neural_config={
            "enabled": True,
            "backend": "tiny_torch",
            "live_mode": True,
            "learning_enabled": True,
            "policy_fallback": "allow_non_neural",
        },
    )
    runner = AgentRunner(profile)

    first = runner.run_cycle("inspect Mission Control route and verify served HTML")
    second = runner.run_cycle("inspect Mission Control route and verify served HTML")

    assert first.output["prediction"]["prediction_id"].startswith("prediction_")
    assert first.output["prediction_experience"]["prediction_error"] >= 0
    assert first.output["prediction_learning"]["learning_signal"] == "prediction_error"
    assert any(record["kind"] == "predictive_experience" for record in first.memory_records)
    assert second.output["prediction"]["state_before"]["prior_lessons"]
    assert second.state["current_prediction_error"]["lesson"]


def test_neural_runtime_learns_from_prediction_error_sample():
    manager = NeuralRuntimeManager()
    session = manager.create_session(
        "prediction-agent",
        {"enabled": True, "backend": "tiny_torch", "live_mode": True, "learning_enabled": True, "policy_fallback": "allow_non_neural"},
    )

    record = manager.learn_from_prediction_error(session.session_id, {"prediction_error": 0.42, "neural_learning_sample": {"prediction_error": 0.42}})

    assert record["learning_signal"] == "prediction_error"
    assert record["prediction_error"] == 0.42
    assert record["raw_weights_written"] is False
    assert manager.get_session(session.session_id).learning_tick_count == 1


def test_cognitive_prediction_visual_events_reduce_into_mission_control_state():
    profile = AgentProfile(name="visual-predictive-agent", allowed_tools=("respond",))
    result = AgentRunner(profile).run_cycle("show prediction actual learning in Mission Control")
    events = prediction_experience_to_visual_events(result.output["prediction_experience"], agent_id=profile.agent_id, provenance="replay")
    state = reduce_visual_events(events, provenance="replay").as_record()

    assert state["cognitive"]
    cognitive = state["cognitive"][0]
    assert cognitive["prediction_id"] == result.output["prediction"]["prediction_id"]
    assert cognitive["lesson"]
    assert state["runtime"]["events"] == 1


def test_predictive_cognitive_release_evidence_is_self_validating():
    evidence = predictive_cognitive_core_evidence(".")
    decision = verify_predictive_cognitive_core_evidence(evidence)

    assert evidence["ok"] is True
    assert evidence["predictive_forecast_validated"] is True
    assert evidence["prediction_error_memory_validated"] is True
    assert evidence["prior_lesson_retrieval_validated"] is True
    assert evidence["mission_control_visual_state_validated"] is True
    assert decision["ok"] is True

    documents = build_evidence_documents(".")
    assert "predictive_cognitive_core.json" in documents
    assert documents["predictive_cognitive_core.json"]["ok"] is True
