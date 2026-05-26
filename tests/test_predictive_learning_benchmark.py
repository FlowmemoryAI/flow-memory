import json
import subprocess
import sys

from flow_memory.api.http_server import HttpApiConfig, HttpApiGateway
from flow_memory.api.router import create_default_router
from flow_memory.api.scopes import COGNITION_READ_SCOPE, COGNITION_RUN_SCOPE, COGNITION_WRITE_SCOPE, required_scopes_for
from flow_memory.cognition.benchmarks import benchmark_scenarios, run_predictive_learning_benchmark
from flow_memory.cognition.consolidation import consolidate_experiences, get_lesson, list_lessons
from flow_memory.cognition.telemetry import COGNITION_EVENT_TYPES
from flow_memory.cognition.world_model import DeterministicWorldModel
from flow_memory.flowlang.parser import parse_flowlang
from flow_memory.ir.agent_adapter import agent_profile_from_ir
from flow_memory.release.predictive_learning_evidence import predictive_learning_benchmark_evidence, verify_predictive_learning_benchmark_evidence


FLOWLANG_WITH_PREDICTIVE_LEARNING = """
agent PredictiveLearningAgent {
  goal: "improve predictions over repeated local launch scenarios"

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
    memory_consolidation_enabled: true
    predictive_benchmarks_enabled: true
    confidence_calibration_enabled: true
    explain_predictions: true
  }

  policy {
    autonomy: "supervised"
    requires_approval: true
  }
}
"""


def test_predictive_learning_scenario_registry_contains_required_domains():
    scenario_ids = {scenario["scenario_id"] for scenario in benchmark_scenarios()}

    assert scenario_ids == {
        "dashboard-stale-server",
        "gpu-evidence-import",
        "policy-denial",
        "compute-market-dry-run",
        "git-clean-commit",
    }


def test_dashboard_stale_server_benchmark_improves_after_lesson_reuse(tmp_path):
    result = run_predictive_learning_benchmark(scenario="dashboard-stale-server", trials=4, root=tmp_path)

    assert result["ok"] is True
    assert result["prediction_accuracy_after"] > result["prediction_accuracy_before"]
    assert result["prediction_error_mean_after"] < result["prediction_error_mean_before"]
    assert result["lesson_reuse_rate"] > 0
    assert result["consolidated_lesson_count"] >= 1


def test_all_predictive_learning_scenarios_produce_metrics_and_policy_evidence(tmp_path):
    result = run_predictive_learning_benchmark(scenario="all", trials=3, root=tmp_path)
    scenario_ids = {record["scenario"]["scenario_id"] for record in result["scenario_results"]}

    assert result["ok"] is True
    assert scenario_ids == {scenario["scenario_id"] for scenario in benchmark_scenarios()}
    assert result["metrics"]["prediction_accuracy_after"] >= result["metrics"]["prediction_accuracy_before"]
    assert result["metrics"]["prediction_error_mean_after"] <= result["metrics"]["prediction_error_mean_before"]
    assert result["metrics"]["policy_override_rate"] > 0
    assert result["metrics"]["unsafe_recommendation_rate"] == 0


def test_memory_consolidation_lists_and_reuses_lessons(tmp_path):
    run_predictive_learning_benchmark(scenario="dashboard-stale-server", trials=3, root=tmp_path)
    consolidation = consolidate_experiences(tmp_path)
    lessons = list_lessons(tmp_path)

    assert consolidation["ok"] is True
    assert lessons
    lesson = get_lesson(lessons[0]["lesson_id"], tmp_path)
    assert lesson["recommended_future_action"]

    tick = DeterministicWorldModel().tick(
        {
            "agent_id": "lesson-reuse-agent",
            "goal": "verify dashboard is serving real Mission Control after stale placeholder",
            "action": "open mission-control route without checking stale port",
            "write_experience": False,
        },
        root=tmp_path,
    )

    assert tick["lesson_reuse"]["reused"] is True
    assert tick["lesson_reuse"]["lesson_ids"]
    assert tick["selected_action"]["description"] != "open mission-control route without checking stale port"


def test_flowlang_predictive_learning_block_round_trips_to_agent_profile():
    profile = agent_profile_from_ir(parse_flowlang(FLOWLANG_WITH_PREDICTIVE_LEARNING))

    assert profile.cognition_config["predictive_core_enabled"] is True
    assert profile.cognition_config["memory_consolidation_enabled"] is True
    assert profile.cognition_config["predictive_benchmarks_enabled"] is True


def test_api_benchmark_lesson_metrics_endpoints_and_scopes():
    router = create_default_router()
    benchmark = router.dispatch("POST", "/cognition/benchmarks/run", {"scenario": "dashboard-stale-server", "trials": 2})
    lessons = router.dispatch("POST", "/cognition/lessons/consolidate", {})
    metrics = router.dispatch("GET", "/cognition/metrics", None)

    assert benchmark["ok"] is True
    assert lessons["ok"] is True
    assert metrics["ok"] is True
    assert required_scopes_for("POST", "/cognition/benchmarks/run") == (COGNITION_RUN_SCOPE, COGNITION_WRITE_SCOPE)
    assert required_scopes_for("POST", "/cognition/lessons/consolidate") == (COGNITION_WRITE_SCOPE,)
    assert required_scopes_for("GET", "/cognition/metrics") == (COGNITION_READ_SCOPE,)

    gateway = HttpApiGateway(config=HttpApiConfig(require_scopes=True, enable_rate_limit=False))
    body = json.dumps({"scenario": "dashboard-stale-server", "trials": 2}).encode("utf-8")
    denied = gateway.handle("POST", "/cognition/benchmarks/run", {"x-flow-memory-scopes": COGNITION_READ_SCOPE}, body)
    allowed = gateway.handle("POST", "/cognition/benchmarks/run", {"x-flow-memory-scopes": f"{COGNITION_RUN_SCOPE} {COGNITION_WRITE_SCOPE}"}, body)

    assert denied.status == 403
    assert allowed.status == 200
    assert allowed.body["data"]["ok"] is True


def test_visual_learning_events_are_registered():
    for event_type in (
        "cognition_benchmark_started",
        "cognition_benchmark_trial_started",
        "cognition_benchmark_trial_completed",
        "cognition_metric_updated",
        "cognition_lesson_consolidated",
        "cognition_lesson_reused",
        "cognition_prediction_accuracy_improved",
        "cognition_repeated_mistake_detected",
        "cognition_repeated_mistake_reduced",
    ):
        assert event_type in COGNITION_EVENT_TYPES


def test_cli_predictive_learning_commands_work():
    benchmark = _run_cli("cognition", "benchmark", "run", "--scenario", "dashboard-stale-server", "--trials", "2", "--json")
    consolidated = _run_cli("cognition", "lessons", "consolidate", "--json")
    listed = _run_cli("cognition", "lessons", "list", "--json")
    metrics = _run_cli("cognition", "metrics", "--json")

    assert benchmark["ok"] is True
    assert consolidated["ok"] is True
    assert listed["ok"] is True
    assert metrics["ok"] is True
    assert metrics["prediction_accuracy_after"] >= metrics["prediction_accuracy_before"]


def test_predictive_learning_release_evidence_has_required_fields():
    evidence = predictive_learning_benchmark_evidence(".")
    decision = verify_predictive_learning_benchmark_evidence(evidence)

    assert evidence["ok"] is True
    for key in (
        "predictive_learning_benchmark_available",
        "benchmark_scenarios_available",
        "dashboard_stale_server_scenario_available",
        "gpu_evidence_import_scenario_available",
        "policy_denial_scenario_available",
        "compute_market_dry_run_scenario_available",
        "git_clean_commit_scenario_available",
        "prediction_accuracy_metric_available",
        "prediction_error_metric_available",
        "memory_consolidation_available",
        "consolidated_lessons_available",
        "lesson_reuse_available",
        "agent_uses_lessons_before_prediction",
        "repeated_mistake_reduction_validated",
        "policy_gate_remains_authoritative",
        "cli_benchmark_available",
        "api_benchmark_available",
        "mission_control_learning_panel_available",
        "visual_learning_events_available",
        "no_agi_overclaim_invariant",
        "no_consciousness_overclaim_invariant",
        "no_production_autonomy_overclaim_invariant",
        "public_alpha_docs_updated",
    ):
        assert evidence[key] is True
    assert decision["ok"] is True


def _run_cli(*args: str) -> dict:
    completed = subprocess.run([sys.executable, "-m", "flow_memory", *args], check=True, capture_output=True, text=True)
    return json.loads(completed.stdout)
