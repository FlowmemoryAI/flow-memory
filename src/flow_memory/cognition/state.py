"""Structured world-state records for predictive cognition."""
from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Mapping


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def stable_id(prefix: str, *parts: object) -> str:
    digest = hashlib.sha256("\0".join(str(part) for part in parts).encode("utf-8")).hexdigest()[:24]
    return f"{prefix}_{digest}"


@dataclass(frozen=True)
class WorldState:
    state_id: str
    agent_id: str
    run_id: str = ""
    session_id: str = ""
    goal: str = ""
    current_phase: str = "observed"
    repo_state: Mapping[str, Any] = field(default_factory=dict)
    dashboard_state: Mapping[str, Any] = field(default_factory=dict)
    release_state: Mapping[str, Any] = field(default_factory=dict)
    policy_state: Mapping[str, Any] = field(default_factory=dict)
    memory_context: tuple[Mapping[str, Any], ...] = field(default_factory=tuple)
    recent_errors: tuple[str, ...] = field(default_factory=tuple)
    available_tools: tuple[str, ...] = field(default_factory=tuple)
    gpu_evidence_status: str = "unknown"
    uncertainty_score: float = 0.5
    created_at: str = field(default_factory=utc_now)
    human_readable_summary: str = ""
    vector_state: tuple[float, ...] = field(default_factory=tuple)

    def as_record(self) -> dict[str, Any]:
        return {
            "state_id": self.state_id,
            "agent_id": self.agent_id,
            "run_id": self.run_id,
            "session_id": self.session_id,
            "goal": self.goal,
            "current_phase": self.current_phase,
            "repo_state": dict(self.repo_state),
            "dashboard_state": dict(self.dashboard_state),
            "release_state": dict(self.release_state),
            "policy_state": dict(self.policy_state),
            "memory_context": tuple(dict(item) for item in self.memory_context),
            "recent_errors": self.recent_errors,
            "available_tools": self.available_tools,
            "gpu_evidence_status": self.gpu_evidence_status,
            "uncertainty_score": self.uncertainty_score,
            "created_at": self.created_at,
            "human_readable_summary": self.human_readable_summary,
            "vector_state": self.vector_state,
        }


def build_world_state(
    *,
    agent_id: str,
    goal: str,
    run_id: str = "",
    session_id: str = "",
    current_phase: str = "observed",
    repo_state: Mapping[str, Any] | None = None,
    dashboard_state: Mapping[str, Any] | None = None,
    release_state: Mapping[str, Any] | None = None,
    policy_state: Mapping[str, Any] | None = None,
    memory_context: tuple[Mapping[str, Any], ...] = (),
    recent_errors: tuple[str, ...] = (),
    available_tools: tuple[str, ...] = (),
    gpu_evidence_status: str = "unknown",
    uncertainty_score: float = 0.5,
) -> WorldState:
    summary = _summary(goal, current_phase, memory_context, recent_errors, gpu_evidence_status)
    vector = _vector(goal, memory_context, recent_errors, uncertainty_score)
    state_id = stable_id("world_state", agent_id, run_id, session_id, goal, current_phase, summary)
    return WorldState(
        state_id=state_id,
        agent_id=agent_id,
        run_id=run_id,
        session_id=session_id,
        goal=goal,
        current_phase=current_phase,
        repo_state=dict(repo_state or {}),
        dashboard_state=dict(dashboard_state or {}),
        release_state=dict(release_state or {}),
        policy_state=dict(policy_state or {}),
        memory_context=tuple(dict(item) for item in memory_context),
        recent_errors=recent_errors,
        available_tools=available_tools,
        gpu_evidence_status=gpu_evidence_status,
        uncertainty_score=round(_clamp(uncertainty_score), 6),
        human_readable_summary=summary,
        vector_state=vector,
    )


def _summary(goal: str, phase: str, memory_context: tuple[Mapping[str, Any], ...], errors: tuple[str, ...], gpu: str) -> str:
    bits = [f"goal={goal}", f"phase={phase}", f"memories={len(memory_context)}", f"errors={len(errors)}", f"gpu={gpu}"]
    return "; ".join(bits)


def _vector(goal: str, memory_context: tuple[Mapping[str, Any], ...], errors: tuple[str, ...], uncertainty: float) -> tuple[float, ...]:
    return (
        round(min(len(goal), 240) / 240.0, 6),
        round(min(len(memory_context), 10) / 10.0, 6),
        round(min(len(errors), 10) / 10.0, 6),
        round(_clamp(uncertainty), 6),
    )


def _clamp(value: float) -> float:
    return max(0.0, min(1.0, float(value)))
