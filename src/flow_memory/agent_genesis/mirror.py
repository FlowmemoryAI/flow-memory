"""Agent Mirror records make prediction, outcome, and lesson visible."""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Mapping

from flow_memory.cognition.state import stable_id, utc_now

DEFAULT_MIRROR_DIR = Path("artifacts/genesis/mirrors")


@dataclass(frozen=True)
class AgentMirror:
    mirror_id: str
    agent_id: str
    prediction: Mapping[str, Any]
    actual: Mapping[str, Any]
    surprise: str
    lesson: str
    next_time: str
    confidence_change: float
    risk_change: float
    memory_written: bool
    contribution_offer: Mapping[str, Any]
    created_at: str = field(default_factory=utc_now)

    def as_record(self) -> dict[str, Any]:
        return {
            "mirror_id": self.mirror_id,
            "agent_id": self.agent_id,
            "prediction": dict(self.prediction),
            "actual": dict(self.actual),
            "surprise": self.surprise,
            "lesson": self.lesson,
            "next_time": self.next_time,
            "confidence_change": self.confidence_change,
            "risk_change": self.risk_change,
            "memory_written": self.memory_written,
            "contribution_offer": dict(self.contribution_offer),
            "created_at": self.created_at,
        }


def build_mirror(agent_id: str, prediction: Mapping[str, Any], actual: Mapping[str, Any], lesson: str, *, contribution_mode: str = "private_only") -> AgentMirror:
    matched = bool(actual.get("success", True))
    surprise = "prediction matched observed first outcome" if matched else str(actual.get("reason", "observed outcome differed from prediction"))
    next_time = "reuse this verified pattern" if matched else "verify the failed assumption before repeating the action"
    mirror_id = stable_id("agent_mirror", agent_id, str(prediction), str(actual), lesson)
    return AgentMirror(
        mirror_id=mirror_id,
        agent_id=agent_id,
        prediction=prediction,
        actual=actual,
        surprise=surprise,
        lesson=lesson,
        next_time=next_time,
        confidence_change=0.08 if matched else -0.18,
        risk_change=-0.06 if matched else 0.04,
        memory_written=True,
        contribution_offer={"available": contribution_mode != "private_only", "mode": contribution_mode, "raw_private_payload_excluded": True},
    )


def write_mirror(mirror: AgentMirror | Mapping[str, Any], root: str | Path = ".", directory: str | Path = DEFAULT_MIRROR_DIR) -> Mapping[str, Any]:
    payload = mirror.as_record() if isinstance(mirror, AgentMirror) else dict(mirror)
    path = _path(root, directory, str(payload["agent_id"]))
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return {"ok": True, "agent_id": payload["agent_id"], "mirror_id": payload["mirror_id"], "path": _rel(Path(root).resolve(), path), "record": payload}


def get_mirror(agent_id: str, root: str | Path = ".", directory: str | Path = DEFAULT_MIRROR_DIR) -> Mapping[str, Any]:
    path = _path(root, directory, agent_id)
    if not path.exists():
        raise KeyError(f"unknown agent mirror: {agent_id}")
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
