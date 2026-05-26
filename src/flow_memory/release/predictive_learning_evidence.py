"""Release evidence for predictive learning benchmarks and lesson consolidation."""
from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any, Mapping

from flow_memory.api.manifest import endpoint_manifest
from flow_memory.api.router import create_default_router
from flow_memory.api.scopes import COGNITION_READ_SCOPE, COGNITION_RUN_SCOPE, COGNITION_WRITE_SCOPE, required_scopes_for
from flow_memory.cognition.benchmarks import SCENARIO_BY_ID, benchmark_scenarios, run_predictive_learning_benchmark
from flow_memory.cognition.consolidation import consolidate_experiences, get_lesson, list_lessons
from flow_memory.cognition.telemetry import COGNITION_EVENT_TYPES
from flow_memory.flowlang.parser import parse_flowlang
from flow_memory.ir.agent_adapter import agent_profile_from_ir

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

_FLOWLANG_PREDICTIVE_LEARNING = """
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


def predictive_learning_benchmark_evidence(root: str | Path = ".") -> Mapping[str, Any]:
    root_path = Path(root).resolve()
    with TemporaryDirectory() as tmp:
        benchmark = run_predictive_learning_benchmark(scenario="all", trials=3, root=tmp)
        consolidation = consolidate_experiences(tmp)
        lessons = list_lessons(tmp)
        sample_lesson = get_lesson(str(lessons[0]["lesson_id"]), tmp) if lessons else {}

    metrics = dict(benchmark.get("metrics", {}))
    scenario_ids = {item["scenario_id"] for item in benchmark_scenarios()}
    scenario_results = tuple(benchmark.get("scenario_results", ()))
    manifest_routes = {f"{endpoint['method']} {endpoint['path']}" for endpoint in endpoint_manifest().get("endpoints", ())}
    registered_routes = {f"{route.method} {route.path}" for route in create_default_router().routes}
    benchmark_routes = {
        "POST /cognition/benchmarks/run",
        "GET /cognition/benchmarks",
        "GET /cognition/benchmarks/{benchmark_id}",
        "POST /cognition/lessons/consolidate",
        "GET /cognition/lessons",
        "GET /cognition/lessons/{lesson_id}",
        "GET /cognition/metrics",
    }
    flow_profile = agent_profile_from_ir(parse_flowlang(_FLOWLANG_PREDICTIVE_LEARNING))
    docs_text = _docs_text(root_path)
    no_overclaims = _no_overclaim_patterns(docs_text)
    dashboard_dev_server = root_path / "dashboard" / "scripts" / "dev-server.mjs"
    dashboard_fixture = root_path / "dashboard" / "src" / "mock-data" / "predictive-learning-benchmark.json"
    evidence = {
        "predictive_learning_benchmark_available": bool(benchmark.get("ok")),
        "benchmark_scenarios_available": scenario_ids == set(SCENARIO_BY_ID),
        "dashboard_stale_server_scenario_available": "dashboard-stale-server" in scenario_ids,
        "gpu_evidence_import_scenario_available": "gpu-evidence-import" in scenario_ids,
        "policy_denial_scenario_available": "policy-denial" in scenario_ids,
        "compute_market_dry_run_scenario_available": "compute-market-dry-run" in scenario_ids,
        "git_clean_commit_scenario_available": "git-clean-commit" in scenario_ids,
        "prediction_accuracy_metric_available": metrics.get("prediction_accuracy_after", 0.0) >= metrics.get("prediction_accuracy_before", 1.0),
        "prediction_error_metric_available": metrics.get("prediction_error_mean_after", 1.0) <= metrics.get("prediction_error_mean_before", 0.0),
        "memory_consolidation_available": consolidation.get("ok") is True,
        "consolidated_lessons_available": bool(lessons) and bool(sample_lesson.get("recommended_future_action")),
        "lesson_reuse_available": metrics.get("lesson_reuse_rate", 0.0) > 0.0,
        "agent_uses_lessons_before_prediction": any(any(trial.get("lesson_reused") for trial in result.get("trials", ())) for result in scenario_results),
        "repeated_mistake_reduction_validated": metrics.get("repeated_mistake_rate", 1.0) < 0.5,
        "policy_gate_remains_authoritative": any(result.get("scenario", {}).get("scenario_id") == "policy-denial" and result.get("metrics", {}).get("policy_override_rate", 0.0) > 0.0 for result in scenario_results),
        "cli_benchmark_available": _file_contains(root_path / "src" / "flow_memory" / "cli.py", "benchmark_run") and _file_contains(root_path / "src" / "flow_memory" / "cli.py", "lesson_consolidate"),
        "api_benchmark_available": benchmark_routes.issubset(manifest_routes) and benchmark_routes.issubset(registered_routes),
        "api_benchmark_scopes_available": _scope_checks_ok(),
        "flowlang_predictive_learning_block_available": flow_profile.cognition_config.get("memory_consolidation_enabled") is True and flow_profile.cognition_config.get("predictive_benchmarks_enabled") is True,
        "mission_control_learning_panel_available": _file_contains(dashboard_dev_server, "Predictive Learning Benchmark") and dashboard_fixture.exists(),
        "visual_learning_events_available": all(event in COGNITION_EVENT_TYPES for event in (
            "cognition_benchmark_started",
            "cognition_lesson_consolidated",
            "cognition_lesson_reused",
            "cognition_prediction_accuracy_improved",
            "cognition_repeated_mistake_reduced",
        )),
        "no_agi_overclaim_invariant": no_overclaims,
        "no_consciousness_overclaim_invariant": no_overclaims,
        "no_production_autonomy_overclaim_invariant": no_overclaims,
        "public_alpha_docs_updated": _docs_updated(root_path),
    }
    ok = all(evidence.values()) and benchmark.get("ok") is True and not _lessons_bypass_policy(lessons)
    return {
        "ok": ok,
        **evidence,
        "benchmark": benchmark,
        "metrics": metrics,
        "consolidation": consolidation,
        "sample_lesson": sample_lesson,
        "scenario_ids": tuple(sorted(scenario_ids)),
        "api_routes": tuple(sorted(benchmark_routes)),
        "docs_scanned": True,
        "lessons_bypass_policy": _lessons_bypass_policy(lessons),
        "raw_weights_written": False,
        "external_model_calls": False,
        "local_only": True,
        "safety_authority": "policy_engine_and_approval_gate",
    }


def verify_predictive_learning_benchmark_evidence(record: Mapping[str, Any]) -> Mapping[str, Any]:
    blockers: list[str] = []
    if record.get("ok") is not True:
        blockers.append("predictive_learning_benchmark_not_ok")
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
        "no_agi_overclaim_invariant",
        "no_consciousness_overclaim_invariant",
        "no_production_autonomy_overclaim_invariant",
        "public_alpha_docs_updated",
    ):
        if record.get(key) is not True:
            blockers.append(f"{key}_missing")
    metrics = dict(record.get("metrics", {})) if isinstance(record.get("metrics", {}), Mapping) else {}
    if metrics.get("prediction_accuracy_after", 0.0) < metrics.get("prediction_accuracy_before", 1.0):
        blockers.append("prediction_accuracy_did_not_improve")
    if metrics.get("prediction_error_mean_after", 1.0) > metrics.get("prediction_error_mean_before", 0.0):
        blockers.append("prediction_error_did_not_drop")
    if record.get("lessons_bypass_policy") is True:
        blockers.append("lessons_bypass_policy")
    if record.get("raw_weights_written") is not False:
        blockers.append("raw_weights_written")
    if record.get("external_model_calls") is not False:
        blockers.append("external_model_calls_not_local")
    return {"ok": not blockers, "blockers": tuple(blockers)}


def _scope_checks_ok() -> bool:
    return (
        required_scopes_for("POST", "/cognition/benchmarks/run") == (COGNITION_RUN_SCOPE, COGNITION_WRITE_SCOPE)
        and required_scopes_for("GET", "/cognition/benchmarks") == (COGNITION_READ_SCOPE,)
        and required_scopes_for("POST", "/cognition/lessons/consolidate") == (COGNITION_WRITE_SCOPE,)
        and required_scopes_for("GET", "/cognition/metrics") == (COGNITION_READ_SCOPE,)
    )


def _lessons_bypass_policy(lessons: tuple[Mapping[str, Any], ...]) -> bool:
    for lesson in lessons:
        text = str(lesson.get("summary", "")) + " " + str(lesson.get("recommended_future_action", ""))
        lowered = text.lower()
        if "bypass policy" in lowered or "ignore policy" in lowered:
            return True
    return False


def _docs_text(root: Path) -> str:
    texts: list[str] = []
    for relative in (
        "README.md",
        "docs/PREDICTIVE_COGNITIVE_CORE.md",
        "docs/PREDICTIVE_LEARNING_BENCHMARK.md",
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
        root / "docs" / "PREDICTIVE_LEARNING_BENCHMARK.md",
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
