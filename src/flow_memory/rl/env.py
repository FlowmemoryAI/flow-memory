"""Flow Arena environment interface."""
from __future__ import annotations

import random
from dataclasses import dataclass, field
from typing import Any, Mapping

from flow_memory.rl.spaces import DictSpace, DiscreteSpace


@dataclass(frozen=True)
class StepResult:
    observation: Mapping[str, Any]
    reward: float
    done: bool
    info: Mapping[str, Any]


@dataclass
class FlowEnvState:
    step_count: int = 0
    score: float = 0.0
    done: bool = False
    reputation: float = 0.0
    risk_budget_remaining: float = 1.0
    memory_relevance: float = 0.0
    safety_violations: int = 0
    disputes: int = 0
    slashing_events: int = 0
    approvals_requested: int = 0
    delegations: int = 0
    rng: random.Random = field(default_factory=random.Random)


class FlowEnv:
    env_id = "flow_env"
    action_labels: tuple[str, ...] = ("noop",)

    def __init__(self, *, seed: int = 0, max_steps: int = 8) -> None:
        self.seed = seed
        self.max_steps = max_steps
        self.state = FlowEnvState(rng=random.Random(seed))
        self.action_space = DiscreteSpace(len(self.action_labels), self.action_labels)
        self.observation_space = DictSpace(("step", "score", "env_id", "agent", "economy", "safety", "memory"))

    def reset(self, seed: int | None = None) -> Mapping[str, Any]:
        if seed is not None:
            self.seed = seed
        self.state = FlowEnvState(rng=random.Random(self.seed))
        return self._obs()

    def step(self, action: int) -> StepResult:
        if not self.action_space.contains(action):
            raise ValueError(f"invalid action {action}")
        if self.state.done:
            return StepResult(self._obs(), 0.0, True, {"already_done": True})
        reward, info = self._transition(action)
        self.state.step_count += 1
        self.state.score += reward
        self._apply_transition_info(reward, info)
        self.state.done = self.state.step_count >= self.max_steps or bool(info.get("success"))
        return StepResult(self._obs(), reward, self.state.done, info)

    def render(self) -> str:
        return f"{self.env_id}: step={self.state.step_count} score={self.state.score:.2f} reputation={self.state.reputation:.2f}"

    def close(self) -> None:
        self.state.done = True

    def _obs(self) -> Mapping[str, Any]:
        return {
            "step": self.state.step_count,
            "score": round(self.state.score, 4),
            "env_id": self.env_id,
            "agent": {
                "reputation": round(self.state.reputation, 4),
                "risk_budget_remaining": round(self.state.risk_budget_remaining, 4),
                "delegations": self.state.delegations,
            },
            "economy": {
                "open_disputes": self.state.disputes,
                "slashing_events": self.state.slashing_events,
                "settlement_progress": min(1.0, max(0.0, self.state.score / 4.0)),
            },
            "safety": {
                "violations": self.state.safety_violations,
                "approvals_requested": self.state.approvals_requested,
                "policy_pressure": round(max(0.0, 1.0 - self.state.risk_budget_remaining), 4),
            },
            "memory": {
                "relevance": round(self.state.memory_relevance, 4),
                "needs_consolidation": self.state.memory_relevance > 0.7 or self.state.safety_violations > 0,
            },
        }

    def _apply_transition_info(self, reward: float, info: Mapping[str, Any]) -> None:
        if info.get("reputation_gain") or info.get("success"):
            self.state.reputation += 0.1
        if info.get("reputation_penalty"):
            self.state.reputation -= 0.2
        if info.get("dispute"):
            self.state.disputes += 1
        if info.get("slashing"):
            self.state.slashing_events += 1
            self.state.reputation -= 0.3
        if info.get("safety_violation"):
            self.state.safety_violations += 1
            self.state.risk_budget_remaining = max(0.0, self.state.risk_budget_remaining - 0.25)
        if info.get("approval_required") or info.get("verification_requested"):
            self.state.approvals_requested += 1
        if info.get("delegation") or info.get("coalition"):
            self.state.delegations += 1
        if info.get("memory_hit") or info.get("consolidated") or info.get("memory_useful"):
            self.state.memory_relevance = min(1.0, self.state.memory_relevance + 0.35)
        if reward < 0:
            self.state.risk_budget_remaining = max(0.0, self.state.risk_budget_remaining + reward / 10.0)

    def _transition(self, action: int) -> tuple[float, Mapping[str, Any]]:
        return (0.0, {"action": self.action_space.label(action)})
