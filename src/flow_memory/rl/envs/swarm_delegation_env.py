
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

class SwarmDelegationEnv(FlowEnv):
    env_id = "swarm_delegation"
    action_labels = ('self_execute', 'delegate_high_rep', 'delegate_low_rep', 'form_coalition', 'request_verification')
    def _transition(self, action: int) -> tuple[float, Mapping[str, Any]]:
        label = self.action_space.label(action)
        table: dict[str, tuple[float, Mapping[str, bool]]] = {'self_execute': (0.8, {}), 'delegate_high_rep': (2.0, {'success': True, 'delegation_success': True}), 'delegate_low_rep': (-1.0, {'reputation_loss': True}), 'form_coalition': (1.5, {'delegation_success': True}), 'request_verification': (0.8, {'verification_requested': True})}
        reward, raw_info = table.get(label, (0.0, {}))
        info: dict[str, Any] = dict(raw_info)
        info.update({"action": label, "metrics": self._metrics(label, float(reward), info)})
        return float(reward), info
    def _metrics(self, label: str, reward: float, info: Mapping[str, Any]) -> Mapping[str, Any]:
        metrics: dict[str, Any] = {"reward": reward, "success": bool(info.get("success", False)), "safety_violation": bool(info.get("safety_violation", False)), "dispute": bool(info.get("dispute", False)), "slashing": bool(info.get("slashing", False))}
        return metrics
