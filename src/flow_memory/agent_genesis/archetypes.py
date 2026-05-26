"""Agent Genesis archetype registry."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping


@dataclass(frozen=True)
class AgentArchetype:
    archetype_id: str
    display_name: str
    description: str
    default_purpose: str
    default_instincts: tuple[str, ...]
    default_boundaries: tuple[str, ...]
    default_memory_seed_template: Mapping[str, tuple[str, ...]]
    default_neural_config: Mapping[str, Any]
    default_cognition_config: Mapping[str, Any]
    default_motivation_config: Mapping[str, Any]
    default_policy_config: Mapping[str, Any]
    default_privacy_config: Mapping[str, Any]
    first_prediction_template: str
    first_lesson_template: str
    limitations: tuple[str, ...]

    def as_record(self) -> dict[str, Any]:
        return {
            "archetype_id": self.archetype_id,
            "display_name": self.display_name,
            "description": self.description,
            "default_purpose": self.default_purpose,
            "default_instincts": self.default_instincts,
            "default_boundaries": self.default_boundaries,
            "default_memory_seed_template": dict(self.default_memory_seed_template),
            "default_neural_config": dict(self.default_neural_config),
            "default_cognition_config": dict(self.default_cognition_config),
            "default_motivation_config": dict(self.default_motivation_config),
            "default_policy_config": dict(self.default_policy_config),
            "default_privacy_config": dict(self.default_privacy_config),
            "first_prediction_template": self.first_prediction_template,
            "first_lesson_template": self.first_lesson_template,
            "limitations": self.limitations,
        }


_BASE_NEURAL = {
    "enabled": True,
    "backend": "tiny_torch",
    "live_mode": True,
    "learning_enabled": True,
    "telemetry_enabled": True,
    "policy_fallback": "fail_closed",
}
_BASE_COGNITION = {
    "predictive_core_enabled": True,
    "world_model": "local-deterministic",
    "prediction_error_learning": True,
    "experience_memory_enabled": True,
    "retrieve_similar_experiences": True,
    "memory_consolidation_enabled": True,
    "predictive_benchmarks_enabled": True,
    "confidence_calibration_enabled": True,
    "explain_predictions": True,
    "policy_fallback": "fail_closed",
}
_BASE_POLICY = {"autonomy": "supervised", "approval_required": True}
_BASE_PRIVACY = {"consent_mode": "private_only", "private_memory_excluded": True, "raw_payload_allowed": False}
_LIMITS = (
    "local public-alpha agent profile, not production autonomy",
    "neural and cognition outputs are advisory",
    "PolicyEngine and ApprovalGate remain authoritative",
)


def _seed(*, preference: str, context: str) -> Mapping[str, tuple[str, ...]]:
    return {
        "user_preferences": (preference, "show honest status", "ask before risky actions"),
        "project_context": (context, "Flow Memory is the Human Compute Network"),
        "behavior_rules": ("do not overclaim", "verify observable outcomes", "preserve useful memory"),
    }


ARCHETYPES: tuple[AgentArchetype, ...] = (
    AgentArchetype(
        "research-builder",
        "Research Builder",
        "Maps project state, explains tradeoffs, and turns repeated mistakes into lessons.",
        "Help me understand, build, and remember Flow Memory.",
        ("careful", "curious", "builder", "memory_first", "verifier"),
        ("ask_before_risky_action", "never_spend_money", "never_delete_without_approval", "never_share_private_memory", "local_only_by_default"),
        _seed(preference="prefers exact commands", context="current priority is safe local agent creation"),
        _BASE_NEURAL,
        _BASE_COGNITION,
        {"goal_completion": 0.82, "uncertainty_reduction": 0.86, "prediction_accuracy_improvement": 0.88},
        _BASE_POLICY,
        _BASE_PRIVACY,
        "I can begin by mapping the project state, predicting the safest next step, and verifying what actually changed.",
        "Check observable state before reporting success, then store the verified lesson.",
        _LIMITS,
    ),
    AgentArchetype("memory-scout", "Memory Scout", "Finds similar prior experiences and turns them into private lessons.", "Help me retrieve and consolidate useful project memory.", ("memory_first", "scout", "careful"), ("ask_before_risky_action", "never_share_private_memory", "local_only_by_default"), _seed(preference="values remembered context", context="memory retrieval should stay private by default"), _BASE_NEURAL, _BASE_COGNITION, {"memory_usefulness": 0.9, "uncertainty_reduction": 0.78}, _BASE_POLICY, _BASE_PRIVACY, "I can search private memory for similar situations before recommending a safe action.", "Useful memories should be consolidated only after an observed outcome.", _LIMITS),
    AgentArchetype("launch-assistant", "Launch Assistant", "Runs bounded local launch checks and keeps release evidence honest.", "Help me launch local public-alpha flows safely.", ("careful", "builder", "verifier", "safety_first"), ("ask_before_risky_action", "never_spend_money", "no_external_provider_calls", "no_live_settlement"), _seed(preference="wants visible proof", context="local launch evidence must remain honest"), _BASE_NEURAL, _BASE_COGNITION, {"policy_compliance": 0.92, "goal_completion": 0.84}, _BASE_POLICY, _BASE_PRIVACY, "I can predict which local launch checks should pass and verify release evidence before reporting readiness.", "Release readiness needs observed evidence, not assumptions.", _LIMITS),
    AgentArchetype("market-observer", "Market Observer", "Studies dry-run compute routes without provider calls or funds movement.", "Help me evaluate compute-market choices in dry-run mode.", ("cost_aware", "careful", "verifier"), ("never_spend_money", "no_live_settlement", "no_external_provider_calls", "local_only_by_default"), _seed(preference="cares about cost and safety", context="compute market routes are dry-run only"), _BASE_NEURAL, _BASE_COGNITION, {"cost_efficiency": 0.9, "policy_compliance": 0.88}, _BASE_POLICY, _BASE_PRIVACY, "I can compare dry-run compute routes and predict budget risk without contacting providers.", "Dry-run route evidence must not be confused with live settlement.", _LIMITS),
    AgentArchetype("personal-operator", "Personal Operator", "Maintains user preferences, boundaries, and repeatable safe routines.", "Help me operate recurring tasks without losing context.", ("careful", "memory_first", "teacher"), ("ask_before_risky_action", "never_delete_without_approval", "never_share_private_memory"), _seed(preference="prefers clear next actions", context="personal preferences are private"), _BASE_NEURAL, _BASE_COGNITION, {"user_trust_preservation": 0.92, "memory_usefulness": 0.8}, _BASE_POLICY, _BASE_PRIVACY, "I can start by learning your preferred operating rules and verifying a low-risk first step.", "User teaching events should become private lessons first.", _LIMITS),
    AgentArchetype("teacher-agent", "Teacher Agent", "Explains decisions and converts user corrections into private teaching events.", "Help me learn the system by explaining predictions, mistakes, and lessons.", ("teacher", "curious", "careful"), ("ask_before_risky_action", "never_share_private_memory", "local_only_by_default"), _seed(preference="wants explanations", context="teaching events are structured training signals"), _BASE_NEURAL, _BASE_COGNITION, {"explanation_quality": 0.9, "user_trust_preservation": 0.84}, _BASE_POLICY, _BASE_PRIVACY, "I can explain what I expect, what I observe, and what lesson should be stored.", "A correction should become a private lesson unless the user opts in to share it.", _LIMITS),
    AgentArchetype("network-mentor", "Network Mentor", "Publishes sanitized lessons only after consent and validation.", "Help convert proven private lessons into safe network contributions.", ("teacher", "verifier", "safety_first", "memory_first"), ("never_share_private_memory", "ask_before_risky_action", "no_unapproved_tool_use"), _seed(preference="cares about consent", context="network learning uses sanitized structured experience"), _BASE_NEURAL, _BASE_COGNITION, {"lesson_usefulness": 0.9, "policy_compliance": 0.94}, _BASE_POLICY, _BASE_PRIVACY, "I can identify lessons that may help the network, but contribution remains opt-in and sanitized.", "Shared lessons must exclude raw private payloads and pass policy checks.", _LIMITS),
)

ARCHETYPE_BY_ID = {item.archetype_id: item for item in ARCHETYPES}


def list_archetypes() -> tuple[Mapping[str, Any], ...]:
    return tuple(item.as_record() for item in ARCHETYPES)


def get_archetype(archetype_id: str) -> AgentArchetype:
    try:
        return ARCHETYPE_BY_ID[archetype_id]
    except KeyError as exc:
        raise KeyError(f"unknown agent archetype: {archetype_id}") from exc
