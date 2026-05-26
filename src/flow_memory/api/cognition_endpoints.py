"""Predictive cognition endpoint handlers."""
from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping

from flow_memory.agents.profile import AgentProfile
from flow_memory.agents.runner import AgentRunner
from flow_memory.cognition.benchmarks import get_benchmark, latest_benchmark_metrics, list_benchmarks, run_predictive_learning_benchmark
from flow_memory.cognition.consolidation import consolidate_experiences, get_lesson, list_lessons
from flow_memory.cognition.metrics import cognition_metrics
from flow_memory.cognition.experience import get_experience, list_experiences, prediction_error_records, query_experiences
from flow_memory.cognition.world_model import DeterministicWorldModel
from flow_memory.visualization.embodiment import neural_embodiment_state

ROOT = Path(__file__).resolve().parents[3]


def cognition_predict(payload: Mapping[str, Any], root: str | Path = ROOT) -> Mapping[str, Any]:
    model = DeterministicWorldModel()
    state = model.encode_state(payload, root=root)
    memories = query_experiences(str(payload.get("goal", state.goal)), agent_id=str(payload.get("agent_id", payload.get("agent", state.agent_id))), root=root, limit=5)
    actions = model.generate_candidate_actions(state, str(payload.get("action", "")), max_actions=int(payload.get("max_counterfactuals", 4) or 4))
    counterfactuals = model.generate_counterfactuals(state, actions, memories)
    scores = model.score_candidates(actions, counterfactuals, memories)
    return {
        "ok": True,
        "state": state.as_record(),
        "retrieved_memories": memories,
        "candidate_actions": tuple(action.as_record() for action in actions),
        "counterfactuals": counterfactuals.as_record(),
        "predictions": tuple(prediction.as_record() for prediction in counterfactuals.candidate_predictions),
        "scores": tuple(score.as_record() for score in scores),
        "local_only": True,
        "safety_authority": "policy_engine_and_approval_gate",
    }


def cognition_tick(payload: Mapping[str, Any], root: str | Path = ROOT) -> Mapping[str, Any]:
    return DeterministicWorldModel().tick(payload, root=root)


def cognition_experiences(root: str | Path = ROOT) -> Mapping[str, Any]:
    records = list_experiences(root)
    return {"ok": True, "experiences": records, "count": len(records), "local_only": True}


def cognition_experience(experience_id: str, root: str | Path = ROOT) -> Mapping[str, Any]:
    return {"ok": True, "experience": get_experience(experience_id, root), "local_only": True}


def cognition_prediction_errors(root: str | Path = ROOT) -> Mapping[str, Any]:
    errors = prediction_error_records(root)
    return {"ok": True, "prediction_errors": errors, "count": len(errors), "local_only": True}


def cognition_memory_query(payload: Mapping[str, Any], root: str | Path = ROOT) -> Mapping[str, Any]:
    tags_raw = payload.get("tags", ())
    tags = tuple(str(item) for item in tags_raw) if isinstance(tags_raw, (list, tuple)) else tuple(str(tags_raw).split()) if tags_raw else ()
    records = query_experiences(str(payload.get("query", "")), agent_id=str(payload.get("agent_id", "")), tags=tags, root=root, limit=int(payload.get("limit", 10) or 10))
    return {"ok": True, "experiences": records, "count": len(records), "local_only": True}

def cognition_benchmark_run(payload: Mapping[str, Any], root: str | Path = ROOT) -> Mapping[str, Any]:
    return run_predictive_learning_benchmark(
        scenario=str(payload.get("scenario", "all")),
        trials=int(payload.get("trials", 5) or 5),
        root=root,
    )


def cognition_benchmarks(root: str | Path = ROOT) -> Mapping[str, Any]:
    records = list_benchmarks(root)
    return {"ok": True, "benchmarks": records, "count": len(records), "latest_metrics": latest_benchmark_metrics(root), "local_only": True}


def cognition_benchmark(benchmark_id: str, root: str | Path = ROOT) -> Mapping[str, Any]:
    return {"ok": True, "benchmark": get_benchmark(benchmark_id, root), "local_only": True}


def cognition_lessons_consolidate(payload: Mapping[str, Any] | None = None, root: str | Path = ROOT) -> Mapping[str, Any]:
    payload = dict(payload or {})
    return consolidate_experiences(root, min_repetitions=int(payload.get("min_repetitions", 1) or 1))


def cognition_lessons(root: str | Path = ROOT) -> Mapping[str, Any]:
    records = list_lessons(root)
    return {"ok": True, "lessons": records, "count": len(records), "local_only": True}


def cognition_lesson(lesson_id: str, root: str | Path = ROOT) -> Mapping[str, Any]:
    return {"ok": True, "lesson": get_lesson(lesson_id, root), "local_only": True}


def cognition_metrics_endpoint(root: str | Path = ROOT) -> Mapping[str, Any]:
    return cognition_metrics(str(root))


def launch_run_predictions(run_id: str, root: str | Path = ROOT) -> Mapping[str, Any]:
    records = tuple(record for record in list_experiences(root) if record.get("run_id") == run_id or run_id in str(record.get("goal", "")))
    return {"ok": True, "run_id": run_id, "predictions": tuple(record.get("prediction", {}) for record in records), "experiences": records, "local_only": True}


def visual_embodiment_cognition(run_id: str, root: str | Path = ROOT) -> Mapping[str, Any]:
    embodiment = neural_embodiment_state(root, run_id)
    cognition = launch_run_predictions(run_id, root)
    return {"ok": True, "run_id": run_id, "embodiment": embodiment.get("embodiment", {}), "cognition": cognition, "local_only": True}


def cognition_agent_tick(payload: Mapping[str, Any]) -> Mapping[str, Any]:
    profile = AgentProfile(
        name=str(payload.get("agent", payload.get("agent_id", "cognition-agent"))),
        allowed_tools=("respond",),
        neural_config={"enabled": True, "backend": str(payload.get("backend", "tiny_torch")), "live_mode": True, "learning_enabled": True, "policy_fallback": "allow_non_neural"},
        metadata={"cognition": {"predictive_core_enabled": True}},
    )
    result = AgentRunner(profile).run_cycle(str(payload.get("goal", "Explore and report")))
    return {"ok": True, "agent": profile.as_record(), "result": result.as_record(), "local_only": True}
