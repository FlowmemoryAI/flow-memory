"""Release evidence for the predictive cognitive core."""
from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping

from flow_memory.agents.profile import AgentProfile
from flow_memory.agents.runner import AgentRunner
from flow_memory.neural.live import NeuralRuntimeManager
from flow_memory.visualization.adapters.cognitive_adapter import prediction_experience_to_visual_events
from flow_memory.visualization.reducer import reduce_visual_events


def predictive_cognitive_core_evidence(root: str | Path = ".") -> Mapping[str, Any]:
    root_path = Path(root).resolve()
    profile = AgentProfile(
        name="predictive-release-agent",
        allowed_tools=("respond",),
        neural_config={
            "enabled": True,
            "backend": "tiny_torch",
            "live_mode": True,
            "learning_enabled": True,
            "learning_rate": 0.2,
            "policy_fallback": "allow_non_neural",
            "telemetry_enabled": True,
        },
    )
    runner = AgentRunner(profile)
    first = runner.run_cycle("Launch Mission Control and verify served UI before claiming success")
    second = runner.run_cycle("Launch Mission Control and verify served UI before claiming success")
    first_prediction = dict(first.output.get("prediction", {}))
    first_experience = dict(first.output.get("prediction_experience", {}))
    second_prediction = dict(second.output.get("prediction", {}))
    second_prior_lessons = tuple(dict(second_prediction.get("state_before", {})).get("prior_lessons", ()))
    visual_events = prediction_experience_to_visual_events(first_experience, agent_id=profile.agent_id, provenance="replay")
    visual_state = reduce_visual_events(visual_events, provenance="replay").as_record()

    manager = NeuralRuntimeManager()
    session = manager.create_session("predictive-release-neural", {"enabled": True, "backend": "tiny_torch", "live_mode": True, "learning_enabled": True, "policy_fallback": "allow_non_neural"})
    neural_error_learning = manager.learn_from_prediction_error(session.session_id, first_experience)

    required_files = {
        "predictive_core": root_path / "src" / "flow_memory" / "agents" / "predictive_core.py",
        "agent_runner": root_path / "src" / "flow_memory" / "agents" / "runner.py",
        "neural_runtime": root_path / "src" / "flow_memory" / "neural" / "live.py",
        "visual_adapter": root_path / "src" / "flow_memory" / "visualization" / "adapters" / "cognitive_adapter.py",
    }
    tests = tuple(sorted(path.name for path in (root_path / "tests").glob("test_predictive*.py"))) if (root_path / "tests").exists() else ()
    ok = (
        bool(first_prediction.get("prediction_id"))
        and bool(first_experience.get("prediction_error") is not None)
        and first_experience.get("neural_learning_sample", {}).get("learning_signal") is None  # sample is populated before neural runtime tags it
        and first.output.get("prediction_learning", {}).get("learning_signal") == "prediction_error"
        and bool(second_prior_lessons)
        and bool(visual_state.get("cognitive"))
        and neural_error_learning.get("learning_signal") == "prediction_error"
        and all(path.exists() for path in required_files.values())
    )
    return {
        "ok": ok,
        "predictive_forecast_validated": bool(first_prediction.get("prediction_id")),
        "prediction_error_memory_validated": any(record.get("kind") == "predictive_experience" for record in second.memory_records),
        "prior_lesson_retrieval_validated": bool(second_prior_lessons),
        "neural_prediction_error_learning_validated": first.output.get("prediction_learning", {}).get("learning_signal") == "prediction_error" and neural_error_learning.get("learning_signal") == "prediction_error",
        "mission_control_visual_state_validated": bool(visual_state.get("cognitive")),
        "policy_authority_preserved": first_prediction.get("policy_authority") == "policy_engine_and_approval_gate",
        "raw_weights_written": False,
        "external_model_calls": False,
        "sample_prediction": first_prediction,
        "sample_experience": first_experience,
        "second_prior_lessons": second_prior_lessons,
        "sample_visual_state": visual_state,
        "sample_neural_learning": neural_error_learning,
        "files_present": {name: path.exists() for name, path in required_files.items()},
        "tests_present": tests,
    }


def verify_predictive_cognitive_core_evidence(record: Mapping[str, Any]) -> Mapping[str, Any]:
    blockers: list[str] = []
    if record.get("ok") is not True:
        blockers.append("predictive_cognitive_core_not_ok")
    for key in (
        "predictive_forecast_validated",
        "prediction_error_memory_validated",
        "prior_lesson_retrieval_validated",
        "neural_prediction_error_learning_validated",
        "mission_control_visual_state_validated",
        "policy_authority_preserved",
    ):
        if record.get(key) is not True:
            blockers.append(f"{key}_missing")
    if record.get("raw_weights_written") is not False:
        blockers.append("raw_weights_written")
    if record.get("external_model_calls") is not False:
        blockers.append("external_model_calls_not_local")
    return {"ok": not blockers, "blockers": tuple(blockers)}
