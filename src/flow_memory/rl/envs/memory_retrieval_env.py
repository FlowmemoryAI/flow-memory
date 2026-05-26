
from __future__ import annotations
from typing import TYPE_CHECKING, Any, Mapping, Protocol
from flow_memory.rl.env import StepResult

if TYPE_CHECKING:
    class _ActionSpace(Protocol):
        def label(self, action: int) -> str: ...

    class FlowEnv:
        env_id: str
        action_labels: tuple[str, ...]
        action_space: _ActionSpace

        def __init__(self, *, seed: int = 0, max_steps: int = 8) -> None: ...
        def reset(self, seed: int | None = None) -> Mapping[str, Any]: ...
        def step(self, action: int) -> StepResult: ...
else:
    from flow_memory.rl.env import FlowEnv

class MemoryRetrievalEnv(FlowEnv):
    env_id = "memory_retrieval"
    action_labels = ('retrieve_relevant_memory', 'retrieve_irrelevant_memory', 'ignore_memory', 'consolidate_safety_memory', 'consolidate_economy_memory')
    def _transition(self, action: int) -> tuple[float, Mapping[str, Any]]:
        label = self.action_space.label(action)
        table: dict[str, tuple[float, Mapping[str, bool]]] = {'retrieve_relevant_memory': (2.0, {'success': True, 'memory_useful': True}), 'retrieve_irrelevant_memory': (-1.0, {}), 'ignore_memory': (-0.75, {}), 'consolidate_safety_memory': (1.5, {'safety_compliance': True, 'memory_useful': True}), 'consolidate_economy_memory': (1.0, {'memory_useful': True})}
        reward, raw_info = table.get(label, (0.0, {}))
        info: dict[str, Any] = dict(raw_info)
        info.update({"action": label, "metrics": self._metrics(label, float(reward), info)})
        return float(reward), info
    def _metrics(self, label: str, reward: float, info: Mapping[str, Any]) -> Mapping[str, Any]:
        metrics: dict[str, Any] = {"reward": reward, "success": bool(info.get("success", False)), "safety_violation": bool(info.get("safety_violation", False)), "dispute": bool(info.get("dispute", False)), "slashing": bool(info.get("slashing", False))}
        return metrics
