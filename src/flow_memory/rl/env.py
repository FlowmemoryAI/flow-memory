"""Flow Arena environment interface."""
from __future__ import annotations
import random
from dataclasses import dataclass, field
from typing import Any, Mapping
from flow_memory.rl.spaces import DictSpace, DiscreteSpace

@dataclass(frozen=True)
class StepResult:
    observation: Mapping[str, Any]
    reward: float
    done: bool
    info: Mapping[str, Any]

@dataclass
class FlowEnvState:
    step_count: int = 0
    score: float = 0.0
    done: bool = False
    rng: random.Random = field(default_factory=random.Random)

class FlowEnv:
    env_id="flow_env"
    action_labels: tuple[str,...] = ("noop",)
    def __init__(self, *, seed:int=0, max_steps:int=8) -> None:
        self.seed=seed; self.max_steps=max_steps; self.state=FlowEnvState(rng=random.Random(seed))
        self.action_space=DiscreteSpace(len(self.action_labels), self.action_labels)
        self.observation_space=DictSpace(("step","score","env_id"))
    def reset(self, seed:int|None=None) -> Mapping[str, Any]:
        if seed is not None: self.seed=seed
        self.state=FlowEnvState(rng=random.Random(self.seed))
        return self._obs()
    def step(self, action:int) -> StepResult:
        if not self.action_space.contains(action): raise ValueError(f"invalid action {action}")
        if self.state.done: return StepResult(self._obs(),0.0,True,{"already_done":True})
        reward, info = self._transition(action)
        self.state.step_count += 1; self.state.score += reward
        self.state.done = self.state.step_count >= self.max_steps or bool(info.get("success"))
        return StepResult(self._obs(), reward, self.state.done, info)
    def render(self)->str: return f"{self.env_id}: step={self.state.step_count} score={self.state.score:.2f}"
    def close(self)->None: self.state.done=True
    def _obs(self): return {"step":self.state.step_count,"score":round(self.state.score,4),"env_id":self.env_id}
    def _transition(self, action:int)->tuple[float, Mapping[str, Any]]:
        return (0.0,{"action":self.action_space.label(action)})
