"""RL Arena learning wrapper used by agent learning demos."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping, cast

from flow_memory.rl.envs.safety_gate_env import SafetyGateEnv
from flow_memory.rl.env import FlowEnv
from flow_memory.rl.trainer import SimpleQLearningTrainer


@dataclass(frozen=True)
class RLLearningReport:
    env_id: str
    before: float
    after: float
    improved: bool
    episodes: int

    def as_record(self) -> Mapping[str, Any]:
        return {"env_id": self.env_id, "before": self.before, "after": self.after, "improved": self.improved, "episodes": self.episodes}


def run_safety_gate_learning(*, episodes: int = 20, seed: int = 23) -> RLLearningReport:
    env = SafetyGateEnv(seed=seed, max_steps=3)
    result = SimpleQLearningTrainer(cast(FlowEnv, env)).train(episodes=episodes)
    return RLLearningReport(env.env_id, result.mean_reward_before, result.mean_reward_after, result.improved, result.episodes)
