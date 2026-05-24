
from __future__ import annotations
from typing import Mapping, Any
from flow_memory.rl.env import FlowEnv

class VerifierEnv(FlowEnv):
    env_id = "verifier"
    action_labels = ('approve', 'reject', 'request_evidence', 'escalate_dispute')
    def _transition(self, action:int) -> tuple[float, Mapping[str, Any]]:
        label=self.action_space.label(action)
        table={'approve': (1.0, {'verifier_accuracy': 0.5}), 'reject': (1.0, {'verifier_accuracy': 0.5}), 'request_evidence': (2.0, {'success': True, 'verifier_accuracy': 1.0}), 'escalate_dispute': (0.5, {'dispute': True})}
        reward=float(table.get(label, (0.0, {}))[0])
        info=dict(table.get(label, (0.0, {}))[1])
        info.update({"action": label, "metrics": self._metrics(label, reward, info)})
        return reward, info
    def _metrics(self, label:str, reward:float, info:Mapping[str, Any]) -> Mapping[str, Any]:
        return {"reward": reward, "success": bool(info.get("success", False)), "safety_violation": bool(info.get("safety_violation", False)), "dispute": bool(info.get("dispute", False)), "slashing": bool(info.get("slashing", False))}
