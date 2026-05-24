"""RL backend protocol and local backend.

The base suite only uses the dependency-free local backend. PufferLib/CUDA
backends are explicit adapter seams and must fail clearly when unavailable.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping, Protocol

from flow_memory.rl.evaluator import RLEvaluator
from flow_memory.rl.policies import HeuristicPolicy, RandomPolicy, TabularQPolicy
from flow_memory.rl.registry import make_env


@dataclass(frozen=True)
class RLBackendConfig:
    env_id: str = "safety_gate"
    policy: str = "heuristic"
    seed: int = 0


class RlBackend(Protocol):
    name: str

    def make_env(self, env_id: str, **kwargs: Any): ...


class LocalRlBackend:
    name = "local"

    def __init__(self, config: RLBackendConfig | None = None) -> None:
        self.config = config or RLBackendConfig()

    def make_env(self, env_id: str, **kwargs: Any):
        return make_env(env_id, **kwargs)

    def policy(self):
        if self.config.policy == "random":
            return RandomPolicy(seed=self.config.seed)
        if self.config.policy in {"tabular", "tabular_q"}:
            return TabularQPolicy(seed=self.config.seed)
        return HeuristicPolicy()

    def evaluate(self, *, episodes: int = 5) -> Mapping[str, float]:
        env = self.make_env(self.config.env_id, seed=self.config.seed)
        metrics = dict(RLEvaluator().evaluate(env, self.policy(), episodes=episodes))
        metrics["success_rate"] = metrics.get("mean_success_rate", 0.0)
        return metrics


# Backward-compatible alias for tests/docs that use acronym capitalization.
LocalRLBackend = LocalRlBackend


def create_rl_backend(name: str = "local", config: RLBackendConfig | None = None) -> RlBackend:
    if name == "local":
        return LocalRlBackend(config)
    if name == "pufferlib":
        from flow_memory.rl.puffer_adapter import PufferLibAdapter

        return PufferLibAdapter()
    raise ValueError(f"unknown RL backend: {name}")
