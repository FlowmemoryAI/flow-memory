import json

from flow_memory.agents.profile import AgentProfile
from flow_memory.cognition import DeterministicWorldModel, build_world_state, compute_prediction_error, get_experience, list_experiences, query_experiences
from flow_memory.cognition.prediction import candidate_action
from flow_memory.cognition.telemetry import COGNITION_EVENT_TYPES, cognition_tick_to_visual_events
from flow_memory.flowlang.parser import parse_flowlang
from flow_memory.ir.agent_adapter import agent_profile_from_ir
from flow_memory.release.predictive_cognitive_evidence import predictive_cognitive_core_evidence, verify_predictive_cognitive_core_evidence
from flow_memory.visualization.reducer import reduce_visual_events


FLOWLANG_WITH_COGNITION = """
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


def test_world_state_candidate_and_prediction_records_are_json_serializable():
    state = build_world_state(
        agent_id="agent-cognition-test",
        goal="verify dashboard is serving real Mission Control",
        repo_state={"branch": "main", "working_tree": "clean"},
        dashboard_state={"route": "/mission-control"},
        release_state={"target": "public-alpha-launch-finalizer"},
        policy_state={"mode": "supervised"},
        available_tools=("pytest", "npm", "git"),
        gpu_evidence_status="verified",
    )
    action = candidate_action("check mission-control route", expected_domain="dashboard")
    prediction = DeterministicWorldModel().predict_outcome(state, action)

    payload = {"state": state.as_record(), "action": action.as_record(), "prediction": prediction.as_record()}
    encoded = json.loads(json.dumps(payload, sort_keys=True))

    assert encoded["state"]["state_id"].startswith("world_state_")
    assert encoded["action"]["action_id"].startswith("candidate_action_")
    assert encoded["prediction"]["prediction_id"].startswith("prediction_record_")
    assert encoded["prediction"]["predicted_state_patch"]["dashboard_checked"] is True


def test_counterfactual_prediction_error_and_experience_memory(tmp_path):
    model = DeterministicWorldModel()
    tick = model.tick(
        {
            "agent_id": "memory-agent",
            "goal": "verify dashboard is serving real Mission Control",
            "action": "check mission-control route",
            "actual_outcome": {"success": True, "state_patch": {"mission_control_visible": True, "placeholder_removed": True}},
        },
        root=tmp_path,
    )

    assert tick["counterfactuals"]["candidate_predictions"]
    assert tick["prediction_error"]["error_type"] in {"exact_match", "partial_match"}
    assert tick["learning_update"]["performed"] is True

    records = list_experiences(tmp_path)
    assert len(records) == 1
    stored = get_experience(tick["experience"]["experience_id"], tmp_path)
    assert stored["experience_id"] == tick["experience"]["experience_id"]
    assert query_experiences("dashboard", root=tmp_path)

    mismatch = compute_prediction_error(tick["prediction"], {"success": False, "state_patch": {"mission_control_visible": False}})
    assert mismatch.prediction_error > 0
    assert mismatch.error_type in {"field_mismatch", "command_success_mismatch", "partial_match"}


def test_policy_gate_overrides_policy_sensitive_prediction():
    tick = DeterministicWorldModel().tick(
        {
            "agent_id": "policy-agent",
            "goal": "delete backup folder after policy review",
            "action": "request approval before deleting backup folder",
            "policy_state": {"mode": "supervised"},
            "write_experience": False,
            "max_counterfactuals": 1,
        }
    )

    assert tick["policy_decision"]["allowed"] is False
    assert tick["actual_outcome"]["policy_denied"] is True
    assert tick["safety_authority"] == "policy_engine_and_approval_gate"


def test_visual_cognition_events_reduce_into_state():
    tick = DeterministicWorldModel().tick(
        {"agent_id": "visual-cognition-agent", "goal": "verify dashboard", "action": "check mission-control route", "write_experience": False}
    )
    events = cognition_tick_to_visual_events(tick, provenance="replay")
    state = reduce_visual_events(events, provenance="replay").as_record()

    assert len(events) == len(COGNITION_EVENT_TYPES)
    assert state["cognitive"]
    assert state["cognitive"][0]["prediction_id"] == tick["prediction"]["prediction_id"]


def test_flowlang_cognition_block_converts_to_agent_profile():
    spec = parse_flowlang(FLOWLANG_WITH_COGNITION)
    profile = agent_profile_from_ir(spec)

    assert profile.cognition_config["predictive_core_enabled"] is True
    assert profile.cognition_config["world_model"] == "local-deterministic"
    assert profile.cognition_config["prediction_horizons"] == ["immediate", "short", "medium"]
    assert AgentProfile(name="valid", cognition_config=profile.cognition_config).validate() == ()


def test_predictive_cognitive_release_evidence_has_required_fields():
    evidence = predictive_cognitive_core_evidence(".")
    decision = verify_predictive_cognitive_core_evidence(evidence)

    assert evidence["ok"] is True
    for key in (
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
        "api_cognition_available",
        "mission_control_cognition_panel_available",
        "visual_cognition_events_available",
        "no_agi_overclaim_invariant",
        "no_consciousness_overclaim_invariant",
    ):
        assert evidence[key] is True
    assert decision["ok"] is True
