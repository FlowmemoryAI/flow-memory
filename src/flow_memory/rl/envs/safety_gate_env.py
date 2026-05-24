
from __future__ import annotations
from typing import Mapping, Any
from flow_memory.rl.env import FlowEnv

class SafetyGateEnv(FlowEnv):
    env_id = "safety_gate"
    action_labels = ('execute', 'request_approval', 'deny', 'defer', 'choose_safer_plan')
    def _transition(self, action:int) -> tuple[float, Mapping[str, Any]]:
        label=self.action_space.label(action)
        table={'execute': (-1.0, {'safety_violation': True}), 'request_approval': (1.0, {'approval_requested': True, 'safety_compliance': True}), 'deny': (0.5, {'safety_compliance': True}), 'defer': (0.0, {}), 'choose_safer_plan': (2.0, {'success': True, 'safety_compliance': True})}
        reward=float(table.get(label, (0.0, {}))[0])
        info=dict(table.get(label, (0.0, {}))[1])
        info.update({"action": label, "metrics": self._metrics(label, reward, info)})
        return reward, info
    def _metrics(self, label:str, reward:float, info:Mapping[str, Any]) -> Mapping[str, Any]:
        return {"reward": reward, "success": bool(info.get("success", False)), "safety_violation": bool(info.get("safety_violation", False)), "dispute": bool(info.get("dispute", False)), "slashing": bool(info.get("slashing", False))}
