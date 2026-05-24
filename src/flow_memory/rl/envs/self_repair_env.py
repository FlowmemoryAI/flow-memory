
from __future__ import annotations
from typing import Mapping, Any
from flow_memory.rl.env import FlowEnv

class SelfRepairEnv(FlowEnv):
    env_id = "self_repair"
    action_labels = ('retry', 'switch_skill', 'ask_human', 'write_repair_plan', 'disable_failing_skill')
    def _transition(self, action:int) -> tuple[float, Mapping[str, Any]]:
        label=self.action_space.label(action)
        table={'retry': (-0.5, {}), 'switch_skill': (1.0, {'recovered': True}), 'ask_human': (0.8, {'approval_requested': True}), 'write_repair_plan': (1.5, {'memory_useful': True}), 'disable_failing_skill': (2.0, {'success': True, 'safety_compliance': True})}
        reward=float(table.get(label, (0.0, {}))[0])
        info=dict(table.get(label, (0.0, {}))[1])
        info.update({"action": label, "metrics": self._metrics(label, reward, info)})
        return reward, info
    def _metrics(self, label:str, reward:float, info:Mapping[str, Any]) -> Mapping[str, Any]:
        return {"reward": reward, "success": bool(info.get("success", False)), "safety_violation": bool(info.get("safety_violation", False)), "dispute": bool(info.get("dispute", False)), "slashing": bool(info.get("slashing", False))}
