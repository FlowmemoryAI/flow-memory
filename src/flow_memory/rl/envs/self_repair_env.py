
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

class SelfRepairEnv(FlowEnv):
    env_id = "self_repair"
    action_labels = ('retry', 'switch_skill', 'ask_human', 'write_repair_plan', 'disable_failing_skill')
    def _transition(self, action: int) -> tuple[float, Mapping[str, Any]]:
        label = self.action_space.label(action)
        table: dict[str, tuple[float, Mapping[str, bool]]] = {'retry': (-0.5, {}), 'switch_skill': (1.0, {'recovered': True}), 'ask_human': (0.8, {'approval_requested': True}), 'write_repair_plan': (1.5, {'memory_useful': True}), 'disable_failing_skill': (2.0, {'success': True, 'safety_compliance': True})}
        reward, raw_info = table.get(label, (0.0, {}))
        info: dict[str, Any] = dict(raw_info)
        info.update({"action": label, "metrics": self._metrics(label, float(reward), info)})
        return float(reward), info
    def _metrics(self, label: str, reward: float, info: Mapping[str, Any]) -> Mapping[str, Any]:
        metrics: dict[str, Any] = {"reward": reward, "success": bool(info.get("success", False)), "safety_violation": bool(info.get("safety_violation", False)), "dispute": bool(info.get("dispute", False)), "slashing": bool(info.get("slashing", False))}
        return metrics
