"""Experience records and artifact-backed local storage."""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Mapping

from flow_memory.cognition.counterfactuals import CounterfactualSet
from flow_memory.cognition.prediction import CandidateAction, PredictionRecord
from flow_memory.cognition.prediction_error import PredictionErrorRecord
from flow_memory.cognition.state import WorldState, stable_id, utc_now

DEFAULT_EXPERIENCE_DIR = Path("artifacts/cognition/experiences")


@dataclass(frozen=True)
class ExperienceRecord:
    experience_id: str
    agent_id: str
    run_id: str
    session_id: str
    goal: str
    state_before: Mapping[str, Any]
    retrieved_memory_ids: tuple[str, ...]
    candidate_actions: tuple[Mapping[str, Any], ...]
    selected_action: Mapping[str, Any]
    prediction: Mapping[str, Any]
    policy_decision: Mapping[str, Any]
    actual_outcome: Mapping[str, Any]
    prediction_error: Mapping[str, Any]
    lesson: str
    memory_tags: tuple[str, ...]
    confidence_before: float
    confidence_after: float
    risk_before: float
    risk_after: float
    learning_update: Mapping[str, Any]
    created_at: str = field(default_factory=utc_now)

    def as_record(self) -> dict[str, Any]:
        return {
            "experience_id": self.experience_id,
            "agent_id": self.agent_id,
            "run_id": self.run_id,
            "session_id": self.session_id,
            "goal": self.goal,
            "state_before": dict(self.state_before),
            "retrieved_memory_ids": self.retrieved_memory_ids,
            "candidate_actions": tuple(dict(item) for item in self.candidate_actions),
            "selected_action": dict(self.selected_action),
            "prediction": dict(self.prediction),
            "policy_decision": dict(self.policy_decision),
            "actual_outcome": dict(self.actual_outcome),
            "prediction_error": dict(self.prediction_error),
            "lesson": self.lesson,
            "memory_tags": self.memory_tags,
            "confidence_before": self.confidence_before,
            "confidence_after": self.confidence_after,
            "risk_before": self.risk_before,
            "risk_after": self.risk_after,
            "learning_update": dict(self.learning_update),
            "created_at": self.created_at,
        }


def build_experience(
    *,
    state: WorldState | Mapping[str, Any],
    retrieved_memory_ids: tuple[str, ...],
    candidate_actions: tuple[CandidateAction, ...] | tuple[Mapping[str, Any], ...],
    counterfactuals: CounterfactualSet,
    selected_action: CandidateAction | Mapping[str, Any],
    prediction: PredictionRecord | Mapping[str, Any],
    policy_decision: Mapping[str, Any],
    actual_outcome: Mapping[str, Any],
    prediction_error: PredictionErrorRecord | Mapping[str, Any],
    learning_update: Mapping[str, Any] | None = None,
) -> ExperienceRecord:
    state_record = state.as_record() if isinstance(state, WorldState) else dict(state)
    action_record = selected_action.as_record() if isinstance(selected_action, CandidateAction) else dict(selected_action)
    prediction_record = prediction.as_record() if isinstance(prediction, PredictionRecord) else dict(prediction)
    error_record = prediction_error.as_record() if isinstance(prediction_error, PredictionErrorRecord) else dict(prediction_error)
    candidate_records = tuple(item.as_record() if isinstance(item, CandidateAction) else dict(item) for item in candidate_actions)
    agent_id = str(state_record.get("agent_id", prediction_record.get("agent_id", "")))
    goal = str(state_record.get("goal", ""))
    experience_id = stable_id("experience", agent_id, goal, prediction_record.get("prediction_id", ""), error_record.get("error_id", ""))
    return ExperienceRecord(
        experience_id=experience_id,
        agent_id=agent_id,
        run_id=str(state_record.get("run_id", prediction_record.get("run_id", ""))),
        session_id=str(state_record.get("session_id", "")),
        goal=goal,
        state_before=state_record,
        retrieved_memory_ids=retrieved_memory_ids,
        candidate_actions=candidate_records,
        selected_action=action_record,
        prediction=prediction_record,
        policy_decision=dict(policy_decision),
        actual_outcome=dict(actual_outcome),
        prediction_error=error_record,
        lesson=str(error_record.get("lesson", "")),
        memory_tags=_tags(goal, state_record, error_record),
        confidence_before=float(error_record.get("confidence_before", prediction_record.get("confidence", 0.0)) or 0.0),
        confidence_after=float(error_record.get("confidence_after", 0.0) or 0.0),
        risk_before=float(prediction_record.get("risk", 0.0) or 0.0),
        risk_after=max(0.0, float(prediction_record.get("risk", 0.0) or 0.0) - (1.0 - float(error_record.get("prediction_error", 0.0) or 0.0)) * 0.08),
        learning_update=dict(learning_update or {"performed": True, "mode": "local_deterministic", "raw_weights_written": False}),
    )


def write_experience(record: ExperienceRecord | Mapping[str, Any], root: str | Path = ".", directory: str | Path = DEFAULT_EXPERIENCE_DIR) -> Mapping[str, Any]:
    payload = record.as_record() if isinstance(record, ExperienceRecord) else dict(record)
    path = _experience_path(root, directory, str(payload["experience_id"]))
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return {"ok": True, "experience_id": payload["experience_id"], "path": _rel(Path(root).resolve(), path), "record": payload}


def list_experiences(root: str | Path = ".", directory: str | Path = DEFAULT_EXPERIENCE_DIR) -> tuple[Mapping[str, Any], ...]:
    base = Path(root).resolve() / directory
    if not base.exists():
        return ()
    records = []
    for path in sorted(base.glob("*.json")):
        records.append(_read_record(path))
    return tuple(records)


def get_experience(experience_id: str, root: str | Path = ".", directory: str | Path = DEFAULT_EXPERIENCE_DIR) -> Mapping[str, Any]:
    path = _experience_path(root, directory, experience_id)
    if not path.exists():
        raise KeyError(f"unknown experience: {experience_id}")
    return _read_record(path)


def query_experiences(query: str = "", *, agent_id: str = "", tags: tuple[str, ...] = (), root: str | Path = ".", limit: int = 10) -> tuple[Mapping[str, Any], ...]:
    lowered = query.lower().strip()
    tag_set = {tag.lower() for tag in tags}
    matches = []
    for record in list_experiences(root):
        if agent_id and record.get("agent_id") != agent_id:
            continue
        memory_tags = {str(tag).lower() for tag in record.get("memory_tags", ())}
        if tag_set and not tag_set.intersection(memory_tags):
            continue
        text = json.dumps(record, sort_keys=True).lower()
        if lowered and not _query_matches(lowered, text):
            continue
        matches.append(record)
    return tuple(matches[-limit:])


def retrieve_similar_experiences(state: WorldState | Mapping[str, Any], root: str | Path = ".", limit: int = 5) -> tuple[Mapping[str, Any], ...]:
    state_record = state.as_record() if isinstance(state, WorldState) else dict(state)
    query = str(state_record.get("goal", ""))
    tags = tuple(_tags(query, state_record, {}))
    return query_experiences(query, agent_id=str(state_record.get("agent_id", "")), tags=tags, root=root, limit=limit)


def prediction_error_records(root: str | Path = ".") -> tuple[Mapping[str, Any], ...]:
    return tuple(dict(record.get("prediction_error", {})) for record in list_experiences(root) if record.get("prediction_error"))


def _experience_path(root: str | Path, directory: str | Path, experience_id: str) -> Path:
    safe = "".join(ch for ch in experience_id if ch.isalnum() or ch in {"-", "_", "."}).strip(".")
    if not safe:
        raise ValueError("experience_id is required")
    return Path(root).resolve() / directory / f"{safe}.json"


def _read_record(path: Path) -> Mapping[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, Mapping):
        raise ValueError(f"experience is not a JSON object: {path}")
    return dict(payload)


def _tags(goal: str, state: Mapping[str, Any], error: Mapping[str, Any]) -> tuple[str, ...]:
    tags = ["cognition", "prediction", "experience"]
    text = f"{goal} {state} {error}".lower()
    for tag in ("dashboard", "mission-control", "release", "neural", "policy", "compute", "git", "api", "touchdesigner"):
        if tag in text:
            tags.append(tag)
    if float(error.get("prediction_error", 0.0) or 0.0) > 0.5:
        tags.append("high-error")
    return tuple(dict.fromkeys(tags))


def _query_matches(query: str, text: str) -> bool:
    if query in text:
        return True
    tokens = tuple(token for token in query.replace("-", " ").split() if len(token) > 4)
    if not tokens:
        return False
    overlap = sum(1 for token in tokens if token in text)
    return overlap >= min(2, len(tokens))


def _rel(root: Path, path: Path) -> str:
    try:
        return str(path.relative_to(root))
    except ValueError:
        return str(path)
