"""In-process vectorized Flow Arena environments."""
from __future__ import annotations
from typing import Callable
from flow_memory.rl.env import FlowEnv, StepResult

class FlowVectorEnv:
    def __init__(self, factories: tuple[Callable[[], FlowEnv], ...]):
        if not factories: raise ValueError("at least one environment factory is required")
        self.envs=tuple(factory() for factory in factories)
    def reset(self, seed:int|None=None):
        return tuple(env.reset(None if seed is None else seed+i) for i,env in enumerate(self.envs))
    def step(self, actions):
        if len(actions) != len(self.envs): raise ValueError("action batch size mismatch")
        return tuple(env.step(action) for env, action in zip(self.envs, actions))
    def close(self):
        for env in self.envs: env.close()
