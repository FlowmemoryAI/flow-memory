"""Agent Passport records summarize stage, reliability, and contribution posture."""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Mapping

from flow_memory.agent_genesis.stages import calculate_stage
from flow_memory.cognition.state import utc_now

DEFAULT_PASSPORT_DIR = Path("artifacts/genesis/passports")


@dataclass(frozen=True)
class AgentPassport:
    agent_id: str
    stage: str
    genome_id: str
    lessons_learned: int = 0
    predictions_made: int = 0
    prediction_accuracy: float = 0.0
    policy_compliance: float = 1.0
    contributions_made: int = 0
    benchmarks_passed: int = 0
    network_reuse_count: int = 0
    visible_limitations: tuple[str, ...] = ()
    updated_at: str = field(default_factory=utc_now)

    def as_record(self) -> dict[str, Any]:
        return {
            "agent_id": self.agent_id,
            "stage": self.stage,
            "genome_id": self.genome_id,
            "lessons_learned": self.lessons_learned,
            "predictions_made": self.predictions_made,
            "prediction_accuracy": self.prediction_accuracy,
            "policy_compliance": self.policy_compliance,
            "contributions_made": self.contributions_made,
            "benchmarks_passed": self.benchmarks_passed,
            "network_reuse_count": self.network_reuse_count,
            "visible_limitations": self.visible_limitations,
            "updated_at": self.updated_at,
        }


def build_passport(agent_id: str, genome: Mapping[str, Any], metrics: Mapping[str, Any] | None = None) -> AgentPassport:
    data = dict(metrics or {})
    stage = calculate_stage(data)
    return AgentPassport(
        agent_id=agent_id,
        stage=stage,
        genome_id=str(genome.get("genome_id", "")),
        lessons_learned=int(data.get("lessons_learned", data.get("consolidated_lesson_count", 0)) or 0),
        predictions_made=int(data.get("predictions_made", data.get("experience_count", 0)) or 0),
        prediction_accuracy=float(data.get("prediction_accuracy", data.get("prediction_accuracy_after", 0.0)) or 0.0),
        policy_compliance=float(data.get("policy_compliance", 1.0) or 1.0),
        contributions_made=int(data.get("contributions_made", 0) or 0),
        benchmarks_passed=int(data.get("benchmarks_passed", 0) or 0),
        network_reuse_count=int(data.get("network_reuse_count", 0) or 0),
        visible_limitations=tuple(str(item) for item in genome.get("limitations", ("local public-alpha; policy-gated",))),
    )


def write_passport(passport: AgentPassport | Mapping[str, Any], root: str | Path = ".", directory: str | Path = DEFAULT_PASSPORT_DIR) -> Mapping[str, Any]:
    payload = passport.as_record() if isinstance(passport, AgentPassport) else dict(passport)
    path = _path(root, directory, str(payload["agent_id"]))
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return {"ok": True, "agent_id": payload["agent_id"], "path": _rel(Path(root).resolve(), path), "record": payload}


def get_passport(agent_id: str, root: str | Path = ".", directory: str | Path = DEFAULT_PASSPORT_DIR) -> Mapping[str, Any]:
    path = _path(root, directory, agent_id)
    if not path.exists():
        raise KeyError(f"unknown agent passport: {agent_id}")
    return json.loads(path.read_text(encoding="utf-8"))


def _path(root: str | Path, directory: str | Path, agent_id: str) -> Path:
    safe = "".join(ch for ch in agent_id if ch.isalnum() or ch in {"-", "_", "."}).strip(".")
    if not safe:
        raise ValueError("agent_id is required")
    return Path(root).resolve() / directory / f"{safe}.json"


def _rel(root: Path, path: Path) -> str:
    try:
        return str(path.relative_to(root))
    except ValueError:
        return str(path)
