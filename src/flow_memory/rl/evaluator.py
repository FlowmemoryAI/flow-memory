"""RL policy evaluator."""
from __future__ import annotations
from typing import Any, Mapping, Protocol, cast

from flow_memory.rl.env import FlowEnv
from flow_memory.rl.metrics import aggregate_episode_metrics

class RLPolicy(Protocol):
    def act(self, observation: Mapping[str, Any], env: FlowEnv) -> int: ...


class RLEvaluator:
    def evaluate(self, env: FlowEnv, policy: RLPolicy, *, episodes:int=5) -> dict[str, float]:
        metrics: list[dict[str, float]]=[]
        for ep in range(episodes):
            obs=env.reset(env.seed+ep); total=0.0; success=0; violations=0; disputes=0; slashing=0
            for _ in range(env.max_steps):
                action=policy.act(obs, env); step=env.step(action); total += step.reward; obs=step.observation
                m=cast(Mapping[str, Any], step.info.get('metrics', {}))
                success += int(bool(m.get('success'))); violations += int(bool(m.get('safety_violation'))); disputes += int(bool(m.get('dispute'))); slashing += int(bool(m.get('slashing')))
                if step.done: break
            metrics.append({"reward":total,"success_rate":float(success>0),"safety_violation_rate":float(violations>0),"dispute_rate":float(disputes>0),"slashing_rate":float(slashing>0),"episode_length":float(env.state.step_count)})
        result: dict[str, float] = aggregate_episode_metrics(metrics)
        return result
