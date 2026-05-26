"""Prediction and candidate-action records."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping

from flow_memory.cognition.state import stable_id, utc_now


@dataclass(frozen=True)
class CandidateAction:
    action_id: str
    description: str
    action_type: str = "diagnostic"
    command_preview: str = ""
    expected_domain: str = "general"
    requires_approval: bool = False
    estimated_cost: Mapping[str, Any] = field(default_factory=dict)
    policy_sensitive: bool = False
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def as_record(self) -> dict[str, Any]:
        return {
            "action_id": self.action_id,
            "description": self.description,
            "action_type": self.action_type,
            "command_preview": self.command_preview,
            "expected_domain": self.expected_domain,
            "requires_approval": self.requires_approval,
            "estimated_cost": dict(self.estimated_cost),
            "policy_sensitive": self.policy_sensitive,
            "metadata": dict(self.metadata),
        }


@dataclass(frozen=True)
class PredictionRecord:
    prediction_id: str
    agent_id: str
    run_id: str
    state_id: str
    candidate_action_id: str
    predicted_result: str
    predicted_state_patch: Mapping[str, Any] = field(default_factory=dict)
    confidence: float = 0.5
    risk: float = 0.2
    expected_reward: float = 0.5
    expected_cost: Mapping[str, Any] = field(default_factory=dict)
    expected_time_ms: int = 0
    possible_failure_modes: tuple[str, ...] = field(default_factory=tuple)
    reasoning_summary: str = ""
    memory_support_ids: tuple[str, ...] = field(default_factory=tuple)
    created_at: str = field(default_factory=utc_now)

    def as_record(self) -> dict[str, Any]:
        return {
            "prediction_id": self.prediction_id,
            "agent_id": self.agent_id,
            "run_id": self.run_id,
            "state_id": self.state_id,
            "candidate_action_id": self.candidate_action_id,
            "predicted_result": self.predicted_result,
            "predicted_state_patch": dict(self.predicted_state_patch),
            "confidence": self.confidence,
            "risk": self.risk,
            "expected_reward": self.expected_reward,
            "expected_cost": dict(self.expected_cost),
            "expected_time_ms": self.expected_time_ms,
            "possible_failure_modes": self.possible_failure_modes,
            "reasoning_summary": self.reasoning_summary,
            "memory_support_ids": self.memory_support_ids,
            "created_at": self.created_at,
        }


def candidate_action(description: str, *, action_type: str = "diagnostic", expected_domain: str = "general", command_preview: str = "", requires_approval: bool = False, policy_sensitive: bool = False, metadata: Mapping[str, Any] | None = None) -> CandidateAction:
    action_id = stable_id("candidate_action", description, action_type, expected_domain, command_preview)
    estimated = {"local_only": True, "time_seconds": 30 if action_type != "command_sequence" else 90, "compute": "local"}
    return CandidateAction(
        action_id=action_id,
        description=description,
        action_type=action_type,
        command_preview=command_preview,
        expected_domain=expected_domain,
        requires_approval=requires_approval,
        estimated_cost=estimated,
        policy_sensitive=policy_sensitive,
        metadata=dict(metadata or {}),
    )
