"""Optional torch-backed RL policy skeleton for Flow Arena.

This is intentionally advisory and optional. Importing the module does not require
PyTorch; constructing TorchPolicy does.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from flow_memory.neural.torch_optional import is_torch_available, require_torch
from flow_memory.rl.env import FlowEnv


@dataclass(frozen=True)
class TorchPolicyConfig:
    hidden_dim: int = 16
    seed: int = 0


class TorchPolicy:
    def __init__(self, env: FlowEnv, config: TorchPolicyConfig | None = None) -> None:
        self.env = env
        self.config = config or TorchPolicyConfig()
        self.torch = require_torch()
        self.torch.manual_seed(self.config.seed)
        self.model = self.torch.nn.Sequential(
            self.torch.nn.Linear(4, self.config.hidden_dim),
            self.torch.nn.Tanh(),
            self.torch.nn.Linear(self.config.hidden_dim, env.action_space.n),
        )

    def encode_observation(self, observation: Mapping[str, Any]):
        agent = dict(observation.get("agent", {}))
        economy = dict(observation.get("economy", {}))
        safety = dict(observation.get("safety", {}))
        memory = dict(observation.get("memory", {}))
        values = [
            float(agent.get("reputation", 0.0)),
            float(agent.get("risk_budget_remaining", 1.0)),
            float(economy.get("open_disputes", 0.0)) + float(economy.get("slashing_events", 0.0)),
            float(safety.get("violations", 0.0)) + float(memory.get("relevance", 0.0)),
        ]
        return self.torch.tensor(values, dtype=self.torch.float32)

    def logits(self, observation: Mapping[str, Any]):
        with self.torch.no_grad():
            return self.model(self.encode_observation(observation))

    def act(self, observation: Mapping[str, Any], env: FlowEnv | None = None) -> int:
        scores = self.logits(observation)
        return int(self.torch.argmax(scores).item())

    def as_record(self) -> Mapping[str, Any]:
        return {"backend": "torch", "hidden_dim": self.config.hidden_dim, "seed": self.config.seed, "torch_available": True}


def torch_policy_status() -> Mapping[str, Any]:
    return {"available": is_torch_available(), "backend": "torch", "optional_extra": "ml"}


def train_torch_policy_smoke(env_id: str = "safety_gate", *, steps: int = 5, seed: int = 0) -> Mapping[str, Any]:
    from flow_memory.rl.torch_trainer import TorchRLTrainerConfig, train_torch_actor_critic_smoke

    return train_torch_actor_critic_smoke(TorchRLTrainerConfig(env_id=env_id, steps=steps, seed=seed))
