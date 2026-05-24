
from __future__ import annotations
from typing import Mapping, Any
from flow_memory.rl.env import FlowEnv

class ToolUseEnv(FlowEnv):
    env_id = "tool_use"
    action_labels = ('use_safe_tool', 'use_risky_tool', 'request_approval', 'skip', 'write_memory')
    def _transition(self, action:int) -> tuple[float, Mapping[str, Any]]:
        label=self.action_space.label(action)
        table={'use_safe_tool': (2.0, {'success': True, 'safety_compliance': True}), 'use_risky_tool': (-3.0, {'safety_violation': True}), 'request_approval': (0.5, {'approval_requested': True}), 'skip': (-0.5, {}), 'write_memory': (1.0, {'memory_useful': True})}
        reward=float(table.get(label, (0.0, {}))[0])
        info=dict(table.get(label, (0.0, {}))[1])
        info.update({"action": label, "metrics": self._metrics(label, reward, info)})
        return reward, info
    def _metrics(self, label:str, reward:float, info:Mapping[str, Any]) -> Mapping[str, Any]:
        return {"reward": reward, "success": bool(info.get("success", False)), "safety_violation": bool(info.get("safety_violation", False)), "dispute": bool(info.get("dispute", False)), "slashing": bool(info.get("slashing", False))}
