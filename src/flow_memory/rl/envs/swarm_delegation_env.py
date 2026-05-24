
from __future__ import annotations
from typing import Mapping, Any
from flow_memory.rl.env import FlowEnv

class SwarmDelegationEnv(FlowEnv):
    env_id = "swarm_delegation"
    action_labels = ('self_execute', 'delegate_high_rep', 'delegate_low_rep', 'form_coalition', 'request_verification')
    def _transition(self, action:int) -> tuple[float, Mapping[str, Any]]:
        label=self.action_space.label(action)
        table={'self_execute': (0.8, {}), 'delegate_high_rep': (2.0, {'success': True, 'delegation_success': True}), 'delegate_low_rep': (-1.0, {'reputation_loss': True}), 'form_coalition': (1.5, {'delegation_success': True}), 'request_verification': (0.8, {'verification_requested': True})}
        reward=float(table.get(label, (0.0, {}))[0])
        info=dict(table.get(label, (0.0, {}))[1])
        info.update({"action": label, "metrics": self._metrics(label, reward, info)})
        return reward, info
    def _metrics(self, label:str, reward:float, info:Mapping[str, Any]) -> Mapping[str, Any]:
        return {"reward": reward, "success": bool(info.get("success", False)), "safety_violation": bool(info.get("safety_violation", False)), "dispute": bool(info.get("dispute", False)), "slashing": bool(info.get("slashing", False))}
