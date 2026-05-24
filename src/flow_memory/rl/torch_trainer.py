"""Optional torch-backed RL smoke trainer for Flow Arena.

This module is an adapter seam, not a production RL stack. It lazy-loads torch,
trains a tiny actor-critic style policy on local Flow Arena environments, and
returns structured skip metadata when torch/CUDA is unavailable.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from flow_memory.neural.torch_optional import OptionalDependencyError, require_torch
from flow_memory.rl.env import FlowEnv
from flow_memory.rl.registry import make_env


@dataclass(frozen=True)
class TorchRLTrainerConfig:
    env_id: str = "safety_gate"
    steps: int = 8
    seed: int = 0
    hidden_dim: int = 16
    learning_rate: float = 0.01
    gamma: float = 0.90
    device: str = "auto"


class TorchActorCriticPolicy:
    def __init__(self, env: FlowEnv, *, hidden_dim: int = 16, seed: int = 0, device: str = "cpu") -> None:
        self.torch = require_torch()
        self.env = env
        self.device = self.torch.device(device)
        self.torch.manual_seed(seed)
        self.encoder_dim = 6
        self.body = self.torch.nn.Sequential(
            self.torch.nn.Linear(self.encoder_dim, hidden_dim),
            self.torch.nn.Tanh(),
        ).to(self.device)
        self.actor = self.torch.nn.Linear(hidden_dim, env.action_space.n).to(self.device)
        self.critic = self.torch.nn.Linear(hidden_dim, 1).to(self.device)

    def encode_observation(self, observation: Mapping[str, Any]):
        agent = dict(observation.get("agent", {}))
        economy = dict(observation.get("economy", {}))
        safety = dict(observation.get("safety", {}))
        memory = dict(observation.get("memory", {}))
        values = [
            float(observation.get("step", 0.0)),
            float(agent.get("reputation", 0.0)),
            float(agent.get("risk_budget_remaining", 1.0)),
            float(economy.get("open_disputes", 0.0)) + float(economy.get("slashing_events", 0.0)),
            float(safety.get("violations", 0.0)) + float(safety.get("approvals_requested", 0.0)),
            float(memory.get("relevance", 0.0)),
        ]
        return self.torch.tensor(values, dtype=self.torch.float32, device=self.device)

    def forward(self, observation: Mapping[str, Any]):
        hidden = self.body(self.encode_observation(observation))
        return self.actor(hidden), self.critic(hidden).squeeze(-1)

    def act(self, observation: Mapping[str, Any], *, greedy: bool = False) -> tuple[int, Any, Any]:
        logits, value = self.forward(observation)
        if greedy:
            action = int(self.torch.argmax(logits).item())
            return action, None, value
        dist = self.torch.distributions.Categorical(logits=logits)
        sample = dist.sample()
        return int(sample.item()), dist.log_prob(sample), value

    def as_record(self) -> Mapping[str, Any]:
        return {"backend": "torch_actor_critic", "env_id": self.env.env_id, "device": str(self.device), "actions": list(self.env.action_labels)}


def _resolve_device(torch: Any, requested: str) -> tuple[str | None, str | None]:
    if requested == "auto":
        return ("cuda" if torch.cuda.is_available() else "cpu"), None
    if requested == "cuda" and not torch.cuda.is_available():
        return None, "CUDA requested but torch.cuda.is_available() is false."
    return requested, None


def evaluate_policy(env: FlowEnv, policy: TorchActorCriticPolicy, *, episodes: int = 3, seed: int = 0) -> Mapping[str, Any]:
    returns: list[float] = []
    successes = 0
    safety_violations = 0
    for episode in range(max(1, episodes)):
        obs = env.reset(seed + episode)
        total = 0.0
        done = False
        while not done:
            action, _, _ = policy.act(obs, greedy=True)
            step = env.step(action)
            total += step.reward
            safety_violations += int(step.info.get("safety_violation", False))
            successes += int(step.info.get("success", False))
            obs = step.observation
            done = step.done
        returns.append(round(total, 6))
    return {
        "episodes": max(1, episodes),
        "mean_return": round(sum(returns) / len(returns), 6),
        "returns": returns,
        "successes": successes,
        "safety_violations": safety_violations,
    }


def train_torch_actor_critic_smoke(config: TorchRLTrainerConfig | None = None) -> Mapping[str, Any]:
    config = config or TorchRLTrainerConfig()
    try:
        torch = require_torch()
    except OptionalDependencyError as exc:
        return {"ok": True, "skipped": True, "reason": str(exc), "backend": "torch_actor_critic"}

    device, device_error = _resolve_device(torch, config.device)
    if device_error is not None:
        return {"ok": True, "skipped": True, "reason": device_error, "backend": "torch_actor_critic", "device": config.device}

    env = make_env(config.env_id, seed=config.seed)
    policy = TorchActorCriticPolicy(env, hidden_dim=config.hidden_dim, seed=config.seed, device=device or "cpu")
    optimizer = torch.optim.Adam(list(policy.body.parameters()) + list(policy.actor.parameters()) + list(policy.critic.parameters()), lr=config.learning_rate)
    before = evaluate_policy(env, policy, episodes=2, seed=config.seed)
    losses: list[float] = []
    returns: list[float] = []
    for step_index in range(max(1, config.steps)):
        obs = env.reset(config.seed + step_index)
        log_probs: list[Any] = []
        values: list[Any] = []
        rewards: list[float] = []
        done = False
        while not done:
            action, log_prob, value = policy.act(obs)
            step = env.step(action)
            if log_prob is not None:
                log_probs.append(log_prob)
                values.append(value)
                rewards.append(float(step.reward))
            obs = step.observation
            done = step.done
        running = 0.0
        targets: list[float] = []
        for reward in reversed(rewards):
            running = reward + config.gamma * running
            targets.append(running)
        targets.reverse()
        if targets:
            target_tensor = torch.tensor(targets, dtype=torch.float32, device=policy.device)
            value_tensor = torch.stack(values)
            advantage = target_tensor - value_tensor.detach()
            actor_loss = -(torch.stack(log_probs) * advantage).mean()
            critic_loss = torch.nn.functional.mse_loss(value_tensor, target_tensor)
            loss = actor_loss + 0.5 * critic_loss
            optimizer.zero_grad()
            loss.backward()
            optimizer.step()
            losses.append(round(float(loss.detach().cpu().item()), 6))
            returns.append(round(sum(rewards), 6))
    after = evaluate_policy(env, policy, episodes=2, seed=config.seed + 100)
    return {
        "ok": True,
        "skipped": False,
        "backend": "torch_actor_critic",
        "env_id": config.env_id,
        "device": str(policy.device),
        "steps": config.steps,
        "losses": losses,
        "episode_returns": returns,
        "before": before,
        "after": after,
        "policy": policy.as_record(),
    }
