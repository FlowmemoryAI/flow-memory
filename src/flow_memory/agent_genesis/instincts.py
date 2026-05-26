"""Product-facing instincts mapped to operational agent drives."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping


@dataclass(frozen=True)
class AgentInstinct:
    instinct_id: str
    display_name: str
    description: str
    drive_weights: Mapping[str, float]
    risk_tolerance: float
    approval_threshold: float
    exploration_tolerance: float
    memory_behavior: str
    prediction_behavior: str
    policy_sensitivity: float

    def as_record(self) -> dict[str, Any]:
        return {
            "instinct_id": self.instinct_id,
            "display_name": self.display_name,
            "description": self.description,
            "drive_weights": dict(self.drive_weights),
            "risk_tolerance": self.risk_tolerance,
            "approval_threshold": self.approval_threshold,
            "exploration_tolerance": self.exploration_tolerance,
            "memory_behavior": self.memory_behavior,
            "prediction_behavior": self.prediction_behavior,
            "policy_sensitivity": self.policy_sensitivity,
        }


INSTINCTS: tuple[AgentInstinct, ...] = (
    AgentInstinct("careful", "Careful", "Prefer verified low-risk actions and ask before irreversible steps.", {"policy_compliance": 0.95, "user_trust_preservation": 0.88}, 0.18, 0.82, 0.28, "store verified lessons", "predict failure modes first", 0.94),
    AgentInstinct("curious", "Curious", "Reduce uncertainty by inspecting context and asking better questions.", {"uncertainty_reduction": 0.92, "memory_exploration": 0.72}, 0.34, 0.64, 0.78, "retrieve broadly", "generate counterfactuals", 0.68),
    AgentInstinct("builder", "Builder", "Complete goals through tests, checks, and observable progress.", {"goal_completion": 0.9, "repeated_mistake_reduction": 0.78}, 0.32, 0.68, 0.52, "store procedural lessons", "predict verification outcomes", 0.72),
    AgentInstinct("memory_first", "Memory-first", "Look for prior experiences before recommending action.", {"memory_usefulness": 0.94, "lesson_reuse": 0.84}, 0.24, 0.72, 0.48, "retrieve before acting", "anchor prediction in lessons", 0.78),
    AgentInstinct("cost_aware", "Cost-aware", "Prefer cheap, dry-run, local paths and avoid waste.", {"cost_efficiency": 0.94, "compute_budget_safety": 0.88}, 0.2, 0.82, 0.35, "record cost lessons", "predict cost before action", 0.86),
    AgentInstinct("safety_first", "Safety-first", "Maximize policy compliance and avoid unapproved side effects.", {"policy_compliance": 1.0, "risk_reduction": 0.92}, 0.12, 0.9, 0.22, "store risk warnings", "predict denial paths", 1.0),
    AgentInstinct("fast_mover", "Fast mover", "Move quickly on reversible low-risk work with verification.", {"goal_completion": 0.86, "time_to_resolution": 0.8}, 0.42, 0.58, 0.62, "store compact lessons", "predict immediate outcome", 0.58),
    AgentInstinct("teacher", "Teacher", "Explain predictions, surprises, and lessons clearly.", {"explanation_quality": 0.92, "user_trust_preservation": 0.82}, 0.24, 0.7, 0.5, "turn corrections into lessons", "explain confidence and risk", 0.74),
    AgentInstinct("scout", "Scout", "Explore unfamiliar local context safely and report what is known.", {"discovery": 0.9, "uncertainty_reduction": 0.84}, 0.3, 0.7, 0.76, "map context memories", "predict information gain", 0.7),
    AgentInstinct("verifier", "Verifier", "Confirm claims with checks before treating them as learned.", {"prediction_accuracy_improvement": 0.94, "verification": 0.9}, 0.18, 0.82, 0.36, "store evidence-backed lessons", "predict and measure actual outcome", 0.9),
)

INSTINCT_BY_ID = {item.instinct_id: item for item in INSTINCTS}


def list_instincts() -> tuple[Mapping[str, Any], ...]:
    return tuple(item.as_record() for item in INSTINCTS)


def get_instinct(instinct_id: str) -> AgentInstinct:
    try:
        return INSTINCT_BY_ID[instinct_id]
    except KeyError as exc:
        raise KeyError(f"unknown agent instinct: {instinct_id}") from exc


def merge_instinct_profiles(instinct_ids: tuple[str, ...]) -> Mapping[str, Any]:
    selected = tuple(get_instinct(item) for item in instinct_ids)
    if not selected:
        return {"drive_weights": {}, "risk_tolerance": 0.25, "approval_threshold": 0.75, "policy_sensitivity": 0.8}
    weights: dict[str, float] = {}
    for instinct in selected:
        for key, value in instinct.drive_weights.items():
            weights[key] = max(weights.get(key, 0.0), float(value))
    return {
        "drive_weights": weights,
        "risk_tolerance": round(sum(item.risk_tolerance for item in selected) / len(selected), 6),
        "approval_threshold": round(sum(item.approval_threshold for item in selected) / len(selected), 6),
        "exploration_tolerance": round(sum(item.exploration_tolerance for item in selected) / len(selected), 6),
        "policy_sensitivity": round(max(item.policy_sensitivity for item in selected), 6),
    }
