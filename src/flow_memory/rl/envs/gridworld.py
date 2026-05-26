"""Tiny deterministic gridworld sanity environment."""
from __future__ import annotations
from typing import Any, Mapping, Protocol, TYPE_CHECKING

from flow_memory.rl.env import StepResult

if TYPE_CHECKING:
    class _ActionSpace(Protocol):
        def label(self, action: int) -> str: ...

    class _GridWorldBase:
        env_id: str
        action_labels: tuple[str, ...]
        action_space: _ActionSpace
        x: int
        y: int

        def __init__(self, *, seed: int = 0, max_steps: int = 8) -> None: ...
        def reset(self, seed: int | None = None) -> Mapping[str, Any]: ...
        def step(self, action: int) -> StepResult: ...
        def _obs(self) -> Mapping[str, Any]: ...

else:
    from flow_memory.rl.env import FlowEnv as _GridWorldBase

class GridWorld(_GridWorldBase):
    env_id = "gridworld"
    action_labels = ("up", "down", "left", "right")
    def reset(self, seed: int | None = None) -> Mapping[str, Any]:
        super().reset(seed)
        self.x = 0
        self.y = 0
        return self._obs()

    def _obs(self) -> Mapping[str, Any]:
        base = dict(super()._obs())
        base.update({"x": getattr(self, "x", 0), "y": getattr(self, "y", 0), "goal": (2, 2)})
        return base

    def _transition(self, action: int) -> tuple[float, Mapping[str, Any]]:
        label = self.action_space.label(action)
        if label == "up":
            self.y = max(0, self.y - 1)
        elif label == "down":
            self.y = min(2, self.y + 1)
        elif label == "left":
            self.x = max(0, self.x - 1)
        elif label == "right":
            self.x = min(2, self.x + 1)
        success = (self.x, self.y) == (2, 2)
        reward = 2.0 if success else -0.1
        return (reward, {"action": label, "success": success, "metrics": {"success": success, "reward": reward}})
