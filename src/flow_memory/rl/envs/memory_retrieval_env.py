
from __future__ import annotations
from typing import Mapping, Any
from flow_memory.rl.env import FlowEnv

class MemoryRetrievalEnv(FlowEnv):
    env_id = "memory_retrieval"
    action_labels = ('retrieve_relevant_memory', 'retrieve_irrelevant_memory', 'ignore_memory', 'consolidate_safety_memory', 'consolidate_economy_memory')
    def _transition(self, action:int) -> tuple[float, Mapping[str, Any]]:
        label=self.action_space.label(action)
        table={'retrieve_relevant_memory': (2.0, {'success': True, 'memory_useful': True}), 'retrieve_irrelevant_memory': (-1.0, {}), 'ignore_memory': (-0.75, {}), 'consolidate_safety_memory': (1.5, {'safety_compliance': True, 'memory_useful': True}), 'consolidate_economy_memory': (1.0, {'memory_useful': True})}
        reward=float(table.get(label, (0.0, {}))[0])
        info=dict(table.get(label, (0.0, {}))[1])
        info.update({"action": label, "metrics": self._metrics(label, reward, info)})
        return reward, info
    def _metrics(self, label:str, reward:float, info:Mapping[str, Any]) -> Mapping[str, Any]:
        return {"reward": reward, "success": bool(info.get("success", False)), "safety_violation": bool(info.get("safety_violation", False)), "dispute": bool(info.get("dispute", False)), "slashing": bool(info.get("slashing", False))}
