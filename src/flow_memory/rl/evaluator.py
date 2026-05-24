"""RL policy evaluator."""
from __future__ import annotations
from flow_memory.rl.metrics import aggregate_episode_metrics

class RLEvaluator:
    def evaluate(self, env, policy, *, episodes:int=5):
        metrics=[]
        for ep in range(episodes):
            obs=env.reset(env.seed+ep); total=0.0; success=0; violations=0; disputes=0; slashing=0
            for _ in range(env.max_steps):
                action=policy.act(obs, env); step=env.step(action); total += step.reward; obs=step.observation
                m=step.info.get('metrics', {})
                success += int(bool(m.get('success'))); violations += int(bool(m.get('safety_violation'))); disputes += int(bool(m.get('dispute'))); slashing += int(bool(m.get('slashing')))
                if step.done: break
            metrics.append({"reward":total,"success_rate":float(success>0),"safety_violation_rate":float(violations>0),"dispute_rate":float(disputes>0),"slashing_rate":float(slashing>0),"episode_length":env.state.step_count})
        return aggregate_episode_metrics(metrics)
