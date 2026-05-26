"""In-process vectorized Flow Arena environments."""
from __future__ import annotations
from collections.abc import Callable, Sequence
from typing import Any, Mapping, Protocol

from flow_memory.rl.env import StepResult

class FlowEnv(Protocol):
    def reset(self, seed: int | None = None) -> Mapping[str, Any]: ...
    def step(self, action: int) -> StepResult: ...
    def close(self) -> None: ...


class FlowVectorEnv:
    def __init__(self, factories: Sequence[Callable[[], FlowEnv]]) -> None:
        if not factories:
            raise ValueError("at least one environment factory is required")
        self.envs = tuple(factory() for factory in factories)

    def reset(self, seed: int | None = None) -> tuple[Mapping[str, Any], ...]:
        return tuple(env.reset(None if seed is None else seed + index) for index, env in enumerate(self.envs))

    def step(self, actions: Sequence[int]) -> tuple[StepResult, ...]:
        if len(actions) != len(self.envs):
            raise ValueError("action batch size mismatch")
        return tuple(env.step(action) for env, action in zip(self.envs, actions))

    def close(self) -> None:
        for env in self.envs:
            env.close()
