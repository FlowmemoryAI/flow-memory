"""Agent reputation metrics derived from Proof of Learning records."""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Mapping

from flow_memory.cognition.state import stable_id, utc_now

DEFAULT_REPUTATION_DIR = Path("artifacts/experience_graph/reputation")


@dataclass(frozen=True)
class AgentLearningReputation:
    agent_id: str
    reputation_id: str
    prediction_accuracy: float
    confidence_calibration: float
    policy_compliance: float
    lesson_usefulness: float
    repeated_mistake_reduction: float
    safe_contribution_score: float
    proof_count: int
    reputation_score: float
    created_at: str = field(default_factory=utc_now)

    def as_record(self) -> dict[str, Any]:
        return {
            "agent_id": self.agent_id,
            "reputation_id": self.reputation_id,
            "prediction_accuracy": round(self.prediction_accuracy, 6),
            "confidence_calibration": round(self.confidence_calibration, 6),
            "policy_compliance": round(self.policy_compliance, 6),
            "lesson_usefulness": round(self.lesson_usefulness, 6),
            "repeated_mistake_reduction": round(self.repeated_mistake_reduction, 6),
            "safe_contribution_score": round(self.safe_contribution_score, 6),
            "proof_count": self.proof_count,
            "reputation_score": round(self.reputation_score, 6),
            "created_at": self.created_at,
            "private_payload_excluded": True,
            "safety_authority": "policy_engine_and_approval_gate",
        }


def compute_reputation(proofs: tuple[Mapping[str, Any], ...], graph: Mapping[str, Any] | None = None) -> Mapping[str, Any]:
    grouped: dict[str, list[Mapping[str, Any]]] = {}
    for proof in proofs:
        grouped.setdefault(str(proof.get("agent_id", "network")), []).append(proof)
    records = []
    for agent_id, items in sorted(grouped.items()):
        errors_after = tuple(float(item.get("prediction_error_after", 0.0) or 0.0) for item in items)
        deltas = tuple(float(item.get("error_delta", 0.0) or 0.0) for item in items)
        policy = _mean(float(item.get("policy_compliance", 1.0) or 1.0) for item in items)
        usefulness = _mean(float(item.get("score", 0.0) or 0.0) for item in items)
        safe_contrib = _mean(1.0 if item.get("private_payload_excluded") is True else 0.0 for item in items)
        accuracy = max(0.0, min(1.0, 1.0 - _mean(errors_after)))
        mistake_reduction = max(0.0, min(1.0, _mean(deltas)))
        calibration = max(0.0, min(1.0, 0.5 + (accuracy - _mean(errors_after)) / 2.0))
        score = max(0.0, min(1.0, accuracy * 0.32 + policy * 0.22 + usefulness * 0.2 + mistake_reduction * 0.16 + safe_contrib * 0.1))
        records.append(AgentLearningReputation(
            agent_id=agent_id,
            reputation_id=stable_id("learning_reputation", agent_id, str(len(items)), str(score)),
            prediction_accuracy=accuracy,
            confidence_calibration=calibration,
            policy_compliance=policy,
            lesson_usefulness=usefulness,
            repeated_mistake_reduction=mistake_reduction,
            safe_contribution_score=safe_contrib,
            proof_count=len(items),
            reputation_score=score,
        ).as_record())
    if not records:
        records.append(AgentLearningReputation(
            agent_id="network",
            reputation_id=stable_id("learning_reputation", "network", "empty"),
            prediction_accuracy=0.0,
            confidence_calibration=0.0,
            policy_compliance=1.0,
            lesson_usefulness=0.0,
            repeated_mistake_reduction=0.0,
            safe_contribution_score=1.0,
            proof_count=0,
            reputation_score=0.32,
        ).as_record())
    return {
        "ok": True,
        "graph_id": (graph or {}).get("graph_id", ""),
        "reputations": tuple(records),
        "agent_count": len(records),
        "private_payload_excluded": True,
        "local_only": True,
    }


def write_reputation_records(record: Mapping[str, Any], root: str | Path = ".", directory: str | Path = DEFAULT_REPUTATION_DIR) -> Mapping[str, Any]:
    root_path = Path(root).resolve()
    base = root_path / directory
    base.mkdir(parents=True, exist_ok=True)
    paths = []
    for item in record.get("reputations", ()):
        if not isinstance(item, Mapping):
            continue
        path = base / f"{_safe(str(item.get('agent_id', 'network')))}.json"
        path.write_text(json.dumps(dict(item), indent=2, sort_keys=True) + "\n", encoding="utf-8")
        paths.append(_rel(root_path, path))
    return {"ok": True, "count": len(paths), "paths": tuple(paths)}


def list_reputations(root: str | Path = ".", directory: str | Path = DEFAULT_REPUTATION_DIR) -> tuple[Mapping[str, Any], ...]:
    base = Path(root).resolve() / directory
    if not base.exists():
        return ()
    return tuple(_read_record(path) for path in sorted(base.glob("*.json")))


def get_reputation(agent_id: str, root: str | Path = ".", directory: str | Path = DEFAULT_REPUTATION_DIR) -> Mapping[str, Any]:
    path = Path(root).resolve() / directory / f"{_safe(agent_id)}.json"
    if not path.exists():
        raise KeyError(f"unknown agent reputation: {agent_id}")
    return _read_record(path)


def _mean(values: Any) -> float:
    numbers = tuple(float(value) for value in values)
    return sum(numbers) / len(numbers) if numbers else 0.0


def _safe(value: str) -> str:
    safe = "".join(ch for ch in value if ch.isalnum() or ch in {"-", "_", "."}).strip(".")
    if not safe:
        raise ValueError("agent_id is required")
    return safe


def _read_record(path: Path) -> Mapping[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, Mapping):
        raise ValueError(f"reputation file is not a JSON object: {path}")
    return dict(payload)


def _rel(root: Path, path: Path) -> str:
    try:
        return str(path.relative_to(root))
    except ValueError:
        return str(path)
