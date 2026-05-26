"""Prediction-driven cognitive core for Flow Memory agents.

This module is intentionally deterministic and local. It does not claim human
consciousness or autonomous authority; it gives agents a structured loop for
anticipation, counterfactuals, prediction error, and lesson memory.
"""
from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from typing import Any, Mapping

from flow_memory.agents.planner import Plan

RISK_WEIGHT: Mapping[str, float] = {
    "low": 0.18,
    "medium": 0.42,
    "high": 0.68,
    "critical": 0.92,
}


@dataclass(frozen=True)
class CognitiveWorldState:
    state_id: str
    agent_id: str
    goal: str
    plan_id: str
    plan_actions: tuple[str, ...]
    risk_level: str
    economic_intent: bool
    context_count: int
    prior_lessons: tuple[str, ...] = field(default_factory=tuple)
    memory_tags: tuple[str, ...] = field(default_factory=tuple)

    def as_record(self) -> dict[str, Any]:
        return {
            "state_id": self.state_id,
            "agent_id": self.agent_id,
            "goal": self.goal,
            "plan_id": self.plan_id,
            "plan_actions": self.plan_actions,
            "risk_level": self.risk_level,
            "economic_intent": self.economic_intent,
            "context_count": self.context_count,
            "prior_lessons": self.prior_lessons,
            "memory_tags": self.memory_tags,
        }


@dataclass(frozen=True)
class CounterfactualOutcome:
    action: str
    predicted_success: float
    risk_score: float
    reward_score: float
    rationale: str

    def as_record(self) -> dict[str, Any]:
        return {
            "action": self.action,
            "predicted_success": self.predicted_success,
            "risk_score": self.risk_score,
            "reward_score": self.reward_score,
            "rationale": self.rationale,
        }


@dataclass(frozen=True)
class PredictiveForecast:
    prediction_id: str
    agent_id: str
    goal: str
    state_before: CognitiveWorldState
    chosen_action: str
    predicted_outcome: str
    predicted_success_probability: float
    confidence: float
    risk_score: float
    reward_score: float
    counterfactuals: tuple[CounterfactualOutcome, ...]
    explanation: str
    policy_authority: str = "policy_engine_and_approval_gate"
    local_only: bool = True

    def as_record(self) -> dict[str, Any]:
        return {
            "prediction_id": self.prediction_id,
            "agent_id": self.agent_id,
            "goal": self.goal,
            "state_before": self.state_before.as_record(),
            "chosen_action": self.chosen_action,
            "predicted_outcome": self.predicted_outcome,
            "predicted_success_probability": self.predicted_success_probability,
            "confidence": self.confidence,
            "risk_score": self.risk_score,
            "reward_score": self.reward_score,
            "counterfactuals": tuple(item.as_record() for item in self.counterfactuals),
            "explanation": self.explanation,
            "policy_authority": self.policy_authority,
            "local_only": self.local_only,
        }


@dataclass(frozen=True)
class PredictionExperience:
    experience_id: str
    prediction: PredictiveForecast
    actual_result: Mapping[str, Any]
    success: bool
    prediction_error: float
    confidence_before: float
    confidence_after: float
    lesson: str
    future_policy: str
    memory_tags: tuple[str, ...]
    neural_learning_sample: Mapping[str, Any]

    def as_record(self) -> dict[str, Any]:
        return {
            "experience_id": self.experience_id,
            "prediction": self.prediction.as_record(),
            "actual_result": dict(self.actual_result),
            "success": self.success,
            "prediction_error": self.prediction_error,
            "confidence_before": self.confidence_before,
            "confidence_after": self.confidence_after,
            "lesson": self.lesson,
            "future_policy": self.future_policy,
            "memory_tags": self.memory_tags,
            "neural_learning_sample": dict(self.neural_learning_sample),
        }


class PredictiveCognitiveCore:
    """Build forecasts, score outcomes, and turn surprises into memory."""

    def observe_state(self, profile: Any, goal: str, plan: Plan, context: tuple[Mapping[str, Any], ...] = ()) -> CognitiveWorldState:
        lessons = _prior_lessons(context)
        tags = _memory_tags(goal, plan, lessons)
        state_id = _stable_id(
            "world_state",
            str(getattr(profile, "agent_id", "agent")),
            goal,
            plan.plan_id,
            "|".join(step.action for step in plan.steps),
            str(len(context)),
            "|".join(lessons),
        )
        return CognitiveWorldState(
            state_id=state_id,
            agent_id=str(getattr(profile, "agent_id", "agent")),
            goal=goal,
            plan_id=plan.plan_id,
            plan_actions=tuple(step.action for step in plan.steps),
            risk_level=plan.risk_level,
            economic_intent=plan.economic_intent,
            context_count=len(context),
            prior_lessons=lessons,
            memory_tags=tags,
        )

    def forecast(self, profile: Any, goal: str, plan: Plan, context: tuple[Mapping[str, Any], ...] = ()) -> PredictiveForecast:
        state = self.observe_state(profile, goal, plan, context)
        risk = _plan_risk_score(plan)
        lesson_bonus = min(0.16, len(state.prior_lessons) * 0.04)
        context_bonus = min(0.12, state.context_count * 0.02)
        economic_penalty = 0.08 if plan.economic_intent else 0.0
        predicted_success = _clamp(0.72 + lesson_bonus + context_bonus - risk * 0.45 - economic_penalty)
        confidence = _clamp(0.50 + lesson_bonus + context_bonus + (0.12 if not plan.economic_intent else -0.04) - risk * 0.22)
        reward = _clamp(0.42 + min(0.30, len(plan.steps) * 0.05) + (0.18 if plan.economic_intent else 0.08) - risk * 0.12)
        chosen_action = state.plan_actions[0] if state.plan_actions else "respond"
        prediction_id = _stable_id("prediction", state.state_id, chosen_action, f"{predicted_success:.6f}")
        counterfactuals = self._counterfactuals(plan, risk, reward, lesson_bonus)
        predicted_outcome = _predicted_outcome_text(goal, chosen_action, predicted_success, plan.risk_level)
        explanation = _explanation_text(predicted_success, confidence, risk, state.prior_lessons)
        return PredictiveForecast(
            prediction_id=prediction_id,
            agent_id=state.agent_id,
            goal=goal,
            state_before=state,
            chosen_action=chosen_action,
            predicted_outcome=predicted_outcome,
            predicted_success_probability=round(predicted_success, 6),
            confidence=round(confidence, 6),
            risk_score=round(risk, 6),
            reward_score=round(reward, 6),
            counterfactuals=counterfactuals,
            explanation=explanation,
        )

    def observe_outcome(self, forecast: PredictiveForecast, actual: Mapping[str, Any], evaluation: Mapping[str, Any]) -> PredictionExperience:
        success = bool(actual.get("success", evaluation.get("success", False))) and not bool(actual.get("blocked", False))
        actual_score = 1.0 if success else 0.0
        quality = _number(evaluation.get("quality_score"), 0.0)
        surprise = _number(evaluation.get("surprise_score"), 0.0)
        expected = forecast.predicted_success_probability
        prediction_error = _clamp(abs(expected - actual_score) * 0.70 + surprise * 0.20 + (1.0 - quality) * 0.10)
        confidence_after = _clamp(forecast.confidence * (1.0 - prediction_error * 0.55) + (0.12 if success else -0.08))
        lesson = _lesson_text(forecast, success, prediction_error, actual)
        future_policy = _future_policy_text(forecast, success, prediction_error)
        experience_id = _stable_id("prediction_experience", forecast.prediction_id, str(success), f"{prediction_error:.6f}")
        sample = {
            "prediction_id": forecast.prediction_id,
            "experience_id": experience_id,
            "goal": forecast.goal,
            "chosen_action": forecast.chosen_action,
            "predicted_success_probability": forecast.predicted_success_probability,
            "actual_success": success,
            "prediction_error": round(prediction_error, 6),
            "confidence_before": forecast.confidence,
            "confidence_after": round(confidence_after, 6),
            "lesson": lesson,
            "policy_authority": forecast.policy_authority,
            "local_only": True,
        }
        return PredictionExperience(
            experience_id=experience_id,
            prediction=forecast,
            actual_result=dict(actual),
            success=success,
            prediction_error=round(prediction_error, 6),
            confidence_before=forecast.confidence,
            confidence_after=round(confidence_after, 6),
            lesson=lesson,
            future_policy=future_policy,
            memory_tags=forecast.state_before.memory_tags,
            neural_learning_sample=sample,
        )

    def _counterfactuals(self, plan: Plan, risk: float, reward: float, lesson_bonus: float) -> tuple[CounterfactualOutcome, ...]:
        base_success = _clamp(0.70 + lesson_bonus - risk * 0.35)
        actions = [step.action for step in plan.steps] or ["respond"]
        outcomes = [
            CounterfactualOutcome(
                action=actions[0],
                predicted_success=round(base_success, 6),
                risk_score=round(risk, 6),
                reward_score=round(reward, 6),
                rationale="execute the current policy-gated plan",
            ),
            CounterfactualOutcome(
                action="verify_first",
                predicted_success=round(_clamp(base_success + 0.08), 6),
                risk_score=round(_clamp(risk - 0.12), 6),
                reward_score=round(_clamp(reward - 0.03), 6),
                rationale="reduce uncertainty before irreversible work",
            ),
            CounterfactualOutcome(
                action="request_approval",
                predicted_success=round(_clamp(base_success - 0.04), 6),
                risk_score=round(_clamp(risk - 0.22), 6),
                reward_score=round(_clamp(reward - 0.08), 6),
                rationale="trade speed for policy confidence when risk is elevated",
            ),
        ]
        return tuple(outcomes)


def _prior_lessons(context: tuple[Mapping[str, Any], ...]) -> tuple[str, ...]:
    lessons: list[str] = []
    for record in context:
        payload = record.get("payload", record)
        if not isinstance(payload, Mapping):
            continue
        candidate = payload.get("lesson") or payload.get("future_policy")
        if candidate:
            lessons.append(str(candidate))
    return tuple(dict.fromkeys(lessons[-5:]))


def _memory_tags(goal: str, plan: Plan, lessons: tuple[str, ...]) -> tuple[str, ...]:
    tags = ["predictive", "world-model"]
    lowered = goal.lower()
    for token in ("dashboard", "mission-control", "release", "neural", "touchdesigner", "api", "memory", "policy"):
        if token in lowered:
            tags.append(token)
    if plan.economic_intent:
        tags.append("economic")
    if lessons:
        tags.append("prior-lesson")
    return tuple(dict.fromkeys(tags))


def _plan_risk_score(plan: Plan) -> float:
    risk = RISK_WEIGHT.get(plan.risk_level, 0.75)
    if plan.economic_intent:
        risk = max(risk, 0.62)
    permission_count = len(plan.required_permissions)
    return _clamp(risk + min(0.12, permission_count * 0.015))


def _predicted_outcome_text(goal: str, action: str, probability: float, risk_level: str) -> str:
    if probability >= 0.75:
        expectation = "likely completes the goal"
    elif probability >= 0.55:
        expectation = "may complete the goal with verification"
    else:
        expectation = "is likely to require correction before completion"
    return f"Action {action} {expectation} for {goal!r} under {risk_level} risk."


def _explanation_text(success: float, confidence: float, risk: float, lessons: tuple[str, ...]) -> str:
    lesson_clause = " Prior lessons are available." if lessons else " No prior lesson matched strongly."
    return f"Predicted success {success:.2f}, confidence {confidence:.2f}, risk {risk:.2f}.{lesson_clause}"


def _lesson_text(forecast: PredictiveForecast, success: bool, prediction_error: float, actual: Mapping[str, Any]) -> str:
    if success and prediction_error < 0.35:
        return f"Prediction matched reality for {forecast.chosen_action}; preserve this plan pattern."
    if success:
        return f"Goal succeeded but prediction error was {prediction_error:.2f}; record the hidden variables that changed confidence."
    reason = str(actual.get("reason") or actual.get("output") or "actual outcome diverged")
    return f"Prediction missed for {forecast.chosen_action}: {reason}. Verify assumptions before repeating this action."


def _future_policy_text(forecast: PredictiveForecast, success: bool, prediction_error: float) -> str:
    if success and prediction_error < 0.35:
        return "Prefer this action pattern when the same state, goal, and policy gate recur."
    if prediction_error >= 0.55:
        return "Before acting, retrieve similar prediction-error memories and run an explicit verification step."
    return "Keep the action available, but lower confidence until the missing state variables are observed."


def _stable_id(prefix: str, *parts: str) -> str:
    digest = hashlib.sha256("\0".join(parts).encode("utf-8")).hexdigest()[:24]
    return f"{prefix}_{digest}"


def _number(value: Any, default: float = 0.0) -> float:
    try:
        if value is not None and value != "":
            return float(value)
    except (TypeError, ValueError):
        return default
    return default


def _clamp(value: float) -> float:
    return max(0.0, min(1.0, value))
