"""Simple Q-learning trainer for Flow Arena."""
from __future__ import annotations
from dataclasses import dataclass
from typing import Any, Mapping
from flow_memory.rl.env import FlowEnv
from flow_memory.rl.policies import TabularQPolicy

@dataclass(frozen=True)
class TrainingResult:
    episodes: int
    mean_reward_before: float
    mean_reward_after: float
    improved: bool
    def as_record(self)->Mapping[str, Any]: return {"episodes":self.episodes,"mean_reward_before":self.mean_reward_before,"mean_reward_after":self.mean_reward_after,"improved":self.improved}

class SimpleQLearningTrainer:
    def __init__(self, env:FlowEnv, policy:TabularQPolicy|None=None): self.env=env; self.policy=policy or TabularQPolicy()
    def evaluate_once(self)->float:
        obs=self.env.reset(self.env.seed); total=0.0
        for _ in range(self.env.max_steps):
            action=self.policy.act(obs,self.env); step=self.env.step(action); total += step.reward; obs=step.observation
            if step.done: break
        return total
    def train(self, episodes:int=20)->TrainingResult:
        before=self.evaluate_once(); totals=[]
        for ep in range(episodes):
            obs=self.env.reset(self.env.seed+ep)
            total=0.0
            for step_index in range(self.env.max_steps):
                if step_index == 0 and ep < self.env.action_space.n:
                    action = ep % self.env.action_space.n
                else:
                    action=self.policy.act(obs,self.env)
                step=self.env.step(action)
                self.policy.update(obs, action, step.reward, step.observation, self.env)
                obs=step.observation; total += step.reward
                if step.done: break
            totals.append(total)
        after=sum(totals[-max(1, min(5,len(totals))):])/max(1,min(5,len(totals)))
        return TrainingResult(episodes, before, after, after >= before)
