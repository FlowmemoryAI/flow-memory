"""Tiny deterministic gridworld sanity environment."""
from __future__ import annotations
from typing import Any, Mapping
from flow_memory.rl.env import FlowEnv

class GridWorld(FlowEnv):
    env_id="gridworld"
    action_labels=("up","down","left","right")
    def reset(self, seed:int|None=None)->Mapping[str,Any]:
        obs=super().reset(seed); self.x=0; self.y=0; return self._obs()
    def _obs(self):
        base=dict(super()._obs()); base.update({"x":getattr(self,'x',0),"y":getattr(self,'y',0),"goal":(2,2)}); return base
    def _transition(self, action:int):
        label=self.action_space.label(action)
        if label=="up": self.y=max(0,self.y-1)
        elif label=="down": self.y=min(2,self.y+1)
        elif label=="left": self.x=max(0,self.x-1)
        elif label=="right": self.x=min(2,self.x+1)
        success=(self.x,self.y)==(2,2)
        return (2.0 if success else -0.1, {"action":label,"success":success,"metrics":{"success":success,"reward":2.0 if success else -0.1}})
