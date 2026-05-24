"""Flow Arena configuration."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping


@dataclass(frozen=True)
class FlowArenaConfig:
    env_id: str = "gridworld"
    seed: int = 0
    max_steps: int = 16
    reward_weights: Mapping[str, float] = field(default_factory=dict)
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def validate(self) -> tuple[str, ...]:
        errors: list[str] = []
        if self.max_steps < 1:
            errors.append("max_steps must be positive")
        return tuple(errors)

    def as_record(self) -> Mapping[str, Any]:
        return {
            "env_id": self.env_id,
            "seed": self.seed,
            "max_steps": self.max_steps,
            "reward_weights": dict(self.reward_weights),
            "metadata": dict(self.metadata),
        }


@dataclass(frozen=True)
class RLConfig:
    enabled: bool = False
    backend: str = "local_tabular"
    training_envs: tuple[str, ...] = ("safety_gate",)
    max_training_steps: int = 100
    reward_weights: Mapping[str, float] = field(default_factory=dict)
    safety_authority: str = "policy_engine_and_approval_gate"

    def validate(self) -> tuple[str, ...]:
        errors: list[str] = []
        if self.backend not in {"local_tabular", "tabular_q", "heuristic", "pufferlib"}:
            errors.append(f"unknown RL backend: {self.backend}")
        if self.max_training_steps < 0:
            errors.append("max_training_steps must be non-negative")
        if not self.training_envs:
            errors.append("at least one training env is required")
        if self.safety_authority != "policy_engine_and_approval_gate":
            errors.append("RL safety authority must remain policy_engine_and_approval_gate")
        return tuple(errors)

    def as_record(self) -> Mapping[str, Any]:
        return {
            "enabled": self.enabled,
            "backend": self.backend,
            "training_envs": tuple(self.training_envs),
            "max_training_steps": self.max_training_steps,
            "reward_weights": dict(self.reward_weights),
            "safety_authority": self.safety_authority,
        }
