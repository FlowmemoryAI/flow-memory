"""Agent binding for advisory Flow Arena RL suggestions."""
from __future__ import annotations
from typing import Any, Mapping
from flow_memory.rl.policies import HeuristicPolicy, TabularQPolicy
from flow_memory.rl.registry import make_env

class AgentRlBinding:
    def suggest(self, profile: Any, goal: str) -> Mapping[str, Any]:
        config=dict(getattr(profile, 'rl_config', {}) or {})
        if not config.get('enabled', False):
            return {"enabled": False, "safety_authority": "policy_engine_and_approval_gate"}
        env_id=str((config.get('training_envs') or ['safety_gate'])[0])
        env=make_env(env_id if env_id != 'safety_gate' else 'safety_gate')
        obs=env.reset(int(config.get('seed', 0)))
        policy = HeuristicPolicy() if config.get('backend', 'local_tabular') != 'tabular_q' else TabularQPolicy()
        action=policy.act(obs, env)
        label=env.action_space.label(action)
        return {
            "enabled": True,
            "backend": str(config.get('backend', 'local_tabular')),
            "env_id": env.env_id,
            "suggested_action": label,
            "action_confidence": 0.5 if isinstance(policy, TabularQPolicy) else 0.8,
            "value_estimate": 0.0,
            "reward_prediction": 0.0,
            "uncertainty": 0.5,
            "safety_authority": "policy_engine_and_approval_gate",
        }
