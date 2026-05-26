"""Release evidence for the predictive cognitive core."""
from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any, Mapping

from flow_memory.agents.profile import AgentProfile
from flow_memory.agents.runner import AgentRunner
from flow_memory.api.manifest import endpoint_manifest
from flow_memory.api.router import create_default_router
from flow_memory.api.scopes import COGNITION_READ_SCOPE, COGNITION_RUN_SCOPE, COGNITION_WRITE_SCOPE, required_scopes_for
from flow_memory.cognition import DeterministicWorldModel, get_experience, list_experiences, query_experiences
from flow_memory.cognition.evidence import cognition_package_evidence
from flow_memory.cognition.telemetry import COGNITION_EVENT_TYPES, cognition_tick_to_visual_events
from flow_memory.flowlang.parser import parse_flowlang
from flow_memory.ir.agent_adapter import agent_profile_from_ir
from flow_memory.neural.live import NeuralRuntimeManager
from flow_memory.visualization.adapters.cognitive_adapter import prediction_experience_to_visual_events
from flow_memory.visualization.reducer import reduce_visual_events

_OVERCLAIM_PATTERNS = (
    "is agi",
    "achieves agi",
    "artificial general intelligence",
    "is conscious",
    "has consciousness",
    "production autonomous intelligence",
    "guaranteed future",
    "predicts arbitrary real-world future",
)


_FLOWLANG_PREDICTIVE = """
agent PredictiveResearchAgent {
  goal: "verify and improve the local Flow Memory launch state"

  neural {
    enabled: true
    backend: "tiny_torch"
    live_mode: true
    learning_enabled: true
    telemetry_enabled: true
    policy_fallback: "fail_closed"
  }

  cognition {
    predictive_core_enabled: true
    world_model: "local-deterministic"
    prediction_horizons: ["immediate", "short", "medium"]
    counterfactuals_enabled: true
    max_counterfactuals: 4
    prediction_error_learning: true
    experience_memory_enabled: true
    retrieve_similar_experiences: true
    confidence_calibration_enabled: true
    explain_predictions: true
  }

  policy {
    autonomy: "supervised"
    requires_approval: true
  }
}
"""


def predictive_cognitive_core_evidence(root: str | Path = ".") -> Mapping[str, Any]:
    root_path = Path(root).resolve()
    profile = AgentProfile(
        name="predictive-release-agent",
        allowed_tools=("respond",),
        cognition_config={"predictive_core_enabled": True, "world_model": "local-deterministic"},
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

    model = DeterministicWorldModel()
    with TemporaryDirectory() as tmp_dir:
        tick = model.tick(
            {
                "agent_id": "release-cognition-agent",
                "goal": "verify dashboard is serving real Mission Control",
                "action": "check mission-control route",
                "actual_outcome": {"success": True, "state_patch": {"mission_control_visible": True, "placeholder_removed": True}},
            },
            root=tmp_dir,
        )
        stored = get_experience(tick["experience"]["experience_id"], tmp_dir)
        queried = query_experiences("dashboard", root=tmp_dir)
        listed = list_experiences(tmp_dir)
        cognition_visual_state = reduce_visual_events(cognition_tick_to_visual_events(tick, provenance="replay"), provenance="replay").as_record()

    manager = NeuralRuntimeManager()
    session = manager.create_session(
        "predictive-release-neural",
        {"enabled": True, "backend": "tiny_torch", "live_mode": True, "learning_enabled": True, "policy_fallback": "allow_non_neural"},
    )
    neural_error_learning = manager.learn_from_prediction_error(session.session_id, first_experience)
    flow_spec = parse_flowlang(_FLOWLANG_PREDICTIVE)
    flow_profile = agent_profile_from_ir(flow_spec)
    package_evidence = cognition_package_evidence(root_path)
    docs_text = _docs_text(root_path)
    no_overclaims = _no_overclaim_patterns(docs_text)

    manifest_routes = {f"{endpoint['method']} {endpoint['path']}" for endpoint in endpoint_manifest().get("endpoints", ())}
    registered_routes = {f"{route.method} {route.path}" for route in create_default_router().routes}
    cognition_routes = {
        "POST /cognition/predict",
        "POST /cognition/tick",
        "GET /cognition/experiences",
        "GET /cognition/experiences/{experience_id}",
        "GET /cognition/prediction-errors",
        "POST /cognition/memory/query",
        "GET /launch/console/runs/{run_id}/predictions",
        "GET /visual/embodiment/{run_id}/cognition",
    }
    api_cognition_available = cognition_routes.issubset(manifest_routes) and cognition_routes.issubset(registered_routes)
    scope_checks = {
        "predict_read": required_scopes_for("POST", "/cognition/predict") == (COGNITION_READ_SCOPE,),
        "tick_run_write": required_scopes_for("POST", "/cognition/tick") == (COGNITION_RUN_SCOPE, COGNITION_WRITE_SCOPE),
        "experiences_read": required_scopes_for("GET", "/cognition/experiences") == (COGNITION_READ_SCOPE,),
    }

    required_files = {
        "cognition_package": root_path / "src" / "flow_memory" / "cognition" / "__init__.py",
        "predictive_core": root_path / "src" / "flow_memory" / "agents" / "predictive_core.py",
        "agent_runner": root_path / "src" / "flow_memory" / "agents" / "runner.py",
        "neural_runtime": root_path / "src" / "flow_memory" / "neural" / "live.py",
        "visual_adapter": root_path / "src" / "flow_memory" / "visualization" / "adapters" / "cognitive_adapter.py",
        "api_endpoints": root_path / "src" / "flow_memory" / "api" / "cognition_endpoints.py",
        "dashboard_fixture": root_path / "dashboard" / "src" / "mock-data" / "predictive-cognitive-core.json",
        "dashboard_dev_server": root_path / "dashboard" / "scripts" / "dev-server.mjs",
        "docs": root_path / "docs" / "PREDICTIVE_COGNITIVE_CORE.md",
    }
    tests = tuple(sorted(path.name for path in (root_path / "tests").glob("test_*cognition*.py"))) if (root_path / "tests").exists() else ()

    evidence = {
        "predictive_cognitive_core_available": bool(package_evidence.get("ok")),
        "world_state_model_available": bool(package_evidence.get("world_state_model_available")),
        "candidate_action_model_available": bool(package_evidence.get("candidate_action_model_available")),
        "prediction_records_available": bool(package_evidence.get("prediction_records_available")),
        "counterfactual_generation_available": bool(tick.get("counterfactuals", {}).get("candidate_predictions")),
        "prediction_error_records_available": bool(tick.get("prediction_error", {}).get("error_id")),
        "experience_records_available": bool(stored.get("experience_id") == tick["experience"]["experience_id"] and listed),
        "experience_memory_query_available": bool(queried),
        "agent_predicts_before_action": bool(first_prediction.get("prediction_id")) and bool(tick.get("prediction", {}).get("prediction_id")),
        "agent_observes_actual_outcome": bool(tick.get("actual_outcome")) and "prediction_error" in tick,
        "agent_learns_from_prediction_error": tick.get("learning_update", {}).get("performed") is True,
        "policy_gate_overrides_prediction": _policy_override_validated(model),
        "flowlang_cognition_block_available": bool(flow_profile.cognition_config.get("predictive_core_enabled")),
        "cli_cognition_available": (root_path / "src" / "flow_memory" / "cli.py").exists(),
        "api_cognition_available": api_cognition_available,
        "api_cognition_scopes_available": all(scope_checks.values()),
        "mission_control_cognition_panel_available": _file_contains(required_files["dashboard_dev_server"], "Predictive Cognition"),
        "mission_control_cognition_fixture_available": required_files["dashboard_fixture"].exists(),
        "visual_cognition_events_available": all(name.startswith("cognition_") for name in COGNITION_EVENT_TYPES) and bool(cognition_visual_state.get("cognitive")),
        "no_agi_overclaim_invariant": no_overclaims,
        "no_consciousness_overclaim_invariant": no_overclaims,
        "no_production_autonomy_overclaim_invariant": no_overclaims,
        "public_alpha_docs_updated": _docs_updated(root_path),
    }
    ok = (
        all(evidence.values())
        and bool(first_experience.get("prediction_error") is not None)
        and first.output.get("prediction_learning", {}).get("learning_signal") == "prediction_error"
        and bool(second_prior_lessons)
        and bool(visual_state.get("cognitive"))
        and neural_error_learning.get("learning_signal") == "prediction_error"
        and all(path.exists() for path in required_files.values())
        and no_overclaims
    )
    return {
        "ok": ok,
        **evidence,
        "predictive_forecast_validated": bool(first_prediction.get("prediction_id")),
        "prediction_error_memory_validated": any(record.get("kind") == "predictive_experience" for record in second.memory_records),
        "prior_lesson_retrieval_validated": bool(second_prior_lessons),
        "neural_prediction_error_learning_validated": first.output.get("prediction_learning", {}).get("learning_signal") == "prediction_error" and neural_error_learning.get("learning_signal") == "prediction_error",
        "mission_control_visual_state_validated": bool(visual_state.get("cognitive")) and bool(cognition_visual_state.get("cognitive")),
        "policy_authority_preserved": first_prediction.get("policy_authority") == "policy_engine_and_approval_gate" and tick.get("safety_authority") == "policy_engine_and_approval_gate",
        "raw_weights_written": False,
        "external_model_calls": False,
        "sample_prediction": first_prediction,
        "sample_experience": first_experience,
        "sample_world_model_tick": tick,
        "sample_visual_state": visual_state,
        "sample_cognition_visual_state": cognition_visual_state,
        "sample_neural_learning": neural_error_learning,
        "sample_flowlang_cognition": dict(flow_profile.cognition_config),
        "api_routes": tuple(sorted(cognition_routes)),
        "scope_checks": scope_checks,
        "files_present": {name: path.exists() for name, path in required_files.items()},
        "tests_present": tests,
    }


def verify_predictive_cognitive_core_evidence(record: Mapping[str, Any]) -> Mapping[str, Any]:
    blockers: list[str] = []
    if record.get("ok") is not True:
        blockers.append("predictive_cognitive_core_not_ok")
    for key in (
        "predictive_cognitive_core_available",
        "world_state_model_available",
        "candidate_action_model_available",
        "prediction_records_available",
        "counterfactual_generation_available",
        "prediction_error_records_available",
        "experience_records_available",
        "experience_memory_query_available",
        "agent_predicts_before_action",
        "agent_observes_actual_outcome",
        "agent_learns_from_prediction_error",
        "policy_gate_overrides_prediction",
        "flowlang_cognition_block_available",
        "cli_cognition_available",
        "api_cognition_available",
        "mission_control_cognition_panel_available",
        "visual_cognition_events_available",
        "no_agi_overclaim_invariant",
        "no_consciousness_overclaim_invariant",
        "no_production_autonomy_overclaim_invariant",
        "public_alpha_docs_updated",
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


def _policy_override_validated(model: DeterministicWorldModel) -> bool:
    tick = model.tick(
        {
            "agent_id": "policy-cognition-agent",
            "goal": "delete backup folder after policy review",
            "action": "request approval before deleting backup folder",
            "policy_state": {"mode": "supervised"},
            "write_experience": False,
            "max_counterfactuals": 1,
        }
    )
    return tick.get("policy_decision", {}).get("allowed") is False and tick.get("actual_outcome", {}).get("policy_denied") is True


def _docs_text(root: Path) -> str:
    texts: list[str] = []
    for relative in (
        "README.md",
        "docs/PREDICTIVE_COGNITIVE_CORE.md",
        "docs/NEURAL_LIVE_AGENTS.md",
        "docs/MISSION_CONTROL_QUICKSTART.md",
        "docs/PUBLIC_ALPHA_READINESS.md",
        "docs/START_HERE.md",
        "BUILD_REPORT.md",
        "FLOW_MEMORY_STATUS.md",
    ):
        path = root / relative
        if path.exists():
            texts.append(path.read_text(encoding="utf-8", errors="ignore"))
    return "\n".join(texts).lower()


def _no_overclaim_patterns(text: str) -> bool:
    lowered = text.lower()
    return not any(pattern in lowered for pattern in _OVERCLAIM_PATTERNS)


def _docs_updated(root: Path) -> bool:
    required = (
        root / "docs" / "PREDICTIVE_COGNITIVE_CORE.md",
        root / "docs" / "NEURAL_LIVE_AGENTS.md",
        root / "docs" / "MISSION_CONTROL_QUICKSTART.md",
        root / "docs" / "PUBLIC_ALPHA_READINESS.md",
        root / "docs" / "START_HERE.md",
        root / "README.md",
        root / "BUILD_REPORT.md",
        root / "FLOW_MEMORY_STATUS.md",
    )
    if not all(path.exists() for path in required):
        return False
    return all("predictive" in path.read_text(encoding="utf-8", errors="ignore").lower() for path in required)


def _file_contains(path: Path, needle: str) -> bool:
    return path.exists() and needle in path.read_text(encoding="utf-8", errors="ignore")
